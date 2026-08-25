#!/usr/bin/env python3
"""Fire N parallel `create_bench` calls at one caller's cap and count what got in.

The harness for `specs/.../atomic-admission`. It never reimplements the claim: every request
goes over HTTP to the shipped endpoint, and the only thing this file decides is how many of
them came back admitted.

Three properties make it safe to run against a host that is serving real tenants:

- **It goes to the host's own nginx, not through the CDN.** The public name is behind
  Cloudflare, which answers a dozen simultaneous machine clients with `1010` rather than with
  the endpoint - so the drill would measure the CDN. `BENCHPRESS_URL` overrides it.
- **`queue-long` is stopped for the run** unless `--allow-deploys`. Every deploy is enqueued
  with `enqueue_after_commit=True`, so nothing reaches Redis until the request commits and the
  whole admission decision is still measurable with no worker running. A broken gate then
  admits rows rather than containers.
- **It refuses to run against the wrong site.** `--i-know-this-is` must match the site's own
  `base_domain`, and the drill token must authenticate as the user the setup step just made -
  a token minted on one site does not authenticate on another.
- **Cleanup filters on the drill user and the `drill-` labs**, never on status and never on
  owner alone.

The labs are distinct on purpose. `get_instance_id` is `md5(email + lab)`, so N calls naming
one lab all name one bench, and a same-lab drill would hold at the cap with nothing to admit.

    python3 scripts/admission_drill.py --mode cap --workers 12 --i-know-this-is benchpress.cloud
"""

import argparse
import json
import multiprocessing
import os
import subprocess
import sys
import urllib.error
import urllib.request

SITE = os.environ.get("BENCHPRESS_SITE", "frontend")
COMPOSE_DIR = os.environ.get("BENCHPRESS_COMPOSE_DIR", "/home/ubuntu/benchpress_devops")
BASE_URL = os.environ.get("BENCHPRESS_URL", "http://127.0.0.1:8080")
# nginx routes by `FRAPPE_SITE_NAME_HEADER`, not by this, but a request that names the site it
# means is the one worth measuring.
HOST_HEADER = os.environ.get("BENCHPRESS_HOST", "staging.benchpress.cloud")
DEPLOY_QUEUE = "queue-long"

CREATE_BENCH = "/api/method/benchpress.api.create_bench"
LOGGED_USER = "/api/method/frappe.auth.get_logged_user"

# The sentence `admission.claim` throws. Matched as text because that is all an HTTP client
# gets: Frappe answers every refusal with 417 and the message inside `_server_messages`.
CAP_SENTENCE = "the most your plan allows"

REQUEST_TIMEOUT = 120
BENCH_TIMEOUT = 600


def main() -> int:
	args = _parse_args()
	if args.mode == "cleanup":
		print("cleanup:", json.dumps(_bench_execute("cleanup")))
		return 0

	setup = _bench_execute("setup", workers=args.workers, cap=args.cap)
	_assert_right_site(args.i_know_this_is, setup)

	try:
		return _run(args, setup)
	finally:
		print("restore:", json.dumps(_bench_execute("restore", **_restore_kwargs(setup))))
		if args.cleanup:
			print("cleanup:", json.dumps(_bench_execute("cleanup")))


def _run(args, setup) -> int:
	stopped = _stop_deploy_queue(args.allow_deploys)
	try:
		results = _fire_all(setup)
		# Both before the worker comes back: the counter is what the run produced, and the
		# queued deploys are what the run must not let loose on the host.
		report = _bench_execute("report")
		if stopped:
			print("purged:", json.dumps(_bench_execute("purge_deploy_jobs")))
	finally:
		if stopped:
			_start_deploy_queue()
	return _verdict(args, setup, results, report)


def _fire_all(setup) -> list[dict]:
	"""One process per lab, all released by a barrier so the requests land together.

	Processes rather than threads: `backend` is gunicorn with 2 workers x 4 threads, so eight
	requests are genuinely in flight and the rest queue behind them - which is the contention
	the claim has to survive.
	"""
	context = multiprocessing.get_context("fork")
	barrier = context.Barrier(len(setup["labs"]))
	results = context.Queue()
	headers = {**_auth(setup), "Content-Type": "application/json"}
	workers = [
		context.Process(target=_fire, args=(index, lab, headers, barrier, results))
		for index, lab in enumerate(setup["labs"])
	]
	for worker in workers:
		worker.start()
	collected = [results.get(timeout=REQUEST_TIMEOUT + 60) for _ in workers]
	for worker in workers:
		worker.join(timeout=30)
	return collected


def _fire(index: int, lab: str, headers: dict, barrier, results) -> None:
	request = urllib.request.Request(
		BASE_URL + CREATE_BENCH,
		data=json.dumps({"data": json.dumps({"lab": lab})}).encode(),
		headers=headers,
		method="POST",
	)
	barrier.wait()
	try:
		with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
			results.put(_outcome(index, lab, response.status, response.read()))
	except urllib.error.HTTPError as refusal:
		results.put(_outcome(index, lab, refusal.code, refusal.read()))
	except Exception as failure:  # a transport failure is a drill result too
		results.put({"index": index, "lab": lab, "verdict": "error", "detail": repr(failure)})


def _outcome(index: int, lab: str, status: int, body: bytes) -> dict:
	text = body.decode(errors="replace")
	if status == 200:
		return {"index": index, "lab": lab, "verdict": "admitted", "detail": text[:200]}
	verdict = "refused_cap" if CAP_SENTENCE in text else "refused_other"
	return {"index": index, "lab": lab, "verdict": verdict, "detail": text[:300]}


def _verdict(args, setup, results, report) -> int:
	counts = {verdict: 0 for verdict in ("admitted", "refused_cap", "refused_other", "error")}
	for result in results:
		counts[result["verdict"]] += 1
	expected = args.cap or args.workers

	print(
		f"admitted {counts['admitted']} / attempted {args.workers} · cap {args.cap} · "
		f"refused {counts['refused_cap']} (cap) {counts['refused_other']} (other) · "
		f"{counts['error']} errors"
	)
	print(f"account: active_instances={report['active_instances']} rows={report['admission_rows']}")

	broken = _broken(counts, expected, report)
	sys.stdout.flush()
	for line in broken:
		print(f"FAIL: {line}", file=sys.stderr)
	for result in results:
		if result["verdict"] in ("refused_other", "error"):
			print(f"  {result['lab']}: {result['verdict']} {result['detail']}", file=sys.stderr)
	return 1 if broken else 0


def _broken(counts: dict, expected: int, report: dict) -> list[str]:
	broken = []
	if counts["admitted"] != expected:
		broken.append(f"expected {expected} admitted, got {counts['admitted']}")
	if counts["error"]:
		broken.append(f"{counts['error']} requests failed to complete")
	if counts["refused_other"]:
		broken.append(f"{counts['refused_other']} refused for a reason that is not the cap")
	if report["admission_rows"] != counts["admitted"]:
		broken.append(f"{report['admission_rows']} admission rows for {counts['admitted']} admitted")
	if report["active_instances"] != report["admission_rows"]:
		broken.append(f"counter says {report['active_instances']}, rows say {report['admission_rows']}")
	return broken


def _assert_right_site(claimed: str, setup: dict) -> None:
	if claimed != setup["base_domain"]:
		_refuse(f"this site is {setup['base_domain']!r}, not {claimed!r}")
	logged_in = _logged_user(setup)
	if logged_in != setup["user"]:
		_refuse(f"{BASE_URL} authenticated the drill token as {logged_in!r}, not {setup['user']!r}")


def _logged_user(setup: dict) -> str | None:
	request = urllib.request.Request(BASE_URL + LOGGED_USER, headers=_auth(setup))
	try:
		with urllib.request.urlopen(request, timeout=30) as response:
			return json.loads(response.read()).get("message")
	except Exception as failure:
		_refuse(f"{BASE_URL} would not authenticate the drill token: {failure!r}")


def _auth(setup: dict) -> dict:
	return {
		"Authorization": f"token {setup['api_key']}:{setup['api_secret']}",
		"Host": HOST_HEADER,
	}


def _refuse(reason: str) -> None:
	print(f"refusing to run: {reason}", file=sys.stderr)
	raise SystemExit(2)


def _restore_kwargs(setup: dict) -> dict:
	return {"cap_field": setup["cap_field"], "cap_before": setup["cap_before"]}


def _stop_deploy_queue(allow_deploys: bool) -> bool:
	if allow_deploys:
		print(f"{DEPLOY_QUEUE}: left running (--allow-deploys)")
		return False
	_compose("stop", DEPLOY_QUEUE)
	print(f"{DEPLOY_QUEUE}: stopped for the run")
	return True


def _start_deploy_queue() -> None:
	_compose("start", DEPLOY_QUEUE)
	print(f"{DEPLOY_QUEUE}: started again")


def _compose(*arguments: str) -> None:
	subprocess.run(
		["docker", "compose", *arguments],
		cwd=COMPOSE_DIR,
		check=True,
		stdin=subprocess.DEVNULL,
		timeout=BENCH_TIMEOUT,
	)


def _bench_execute(function: str, **kwargs) -> dict:
	"""Call one `benchpress.credits.drill` function inside the backend container.

	`stdin` is closed deliberately: `docker compose exec` under a timeout hangs forever if it
	inherits a terminal it can read from.
	"""
	command = [
		"docker",
		"compose",
		"exec",
		"-T",
		"backend",
		"bench",
		"--site",
		SITE,
		"execute",
		f"benchpress.credits.drill.{function}",
	]
	if kwargs:
		command += ["--kwargs", json.dumps(kwargs)]
	finished = subprocess.run(
		command,
		cwd=COMPOSE_DIR,
		capture_output=True,
		text=True,
		stdin=subprocess.DEVNULL,
		timeout=BENCH_TIMEOUT,
	)
	if finished.returncode:
		_refuse(f"drill.{function} failed:\n{finished.stdout}\n{finished.stderr}")
	return _last_json(finished.stdout, function)


def _last_json(output: str, function: str) -> dict:
	for line in reversed(output.splitlines()):
		try:
			parsed = json.loads(line)
		except ValueError:
			continue
		if isinstance(parsed, dict):
			return parsed
	_refuse(f"drill.{function} printed nothing that parses:\n{output}")


def _parse_args():
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--mode", choices=("cap", "cleanup"), default="cap")
	parser.add_argument("--workers", type=int, default=12)
	parser.add_argument("--cap", type=int, default=1, help="0 means unlimited")
	parser.add_argument("--i-know-this-is", required=True, help="the site's base_domain")
	parser.add_argument("--allow-deploys", action="store_true", help="leave queue-long running")
	parser.add_argument("--cleanup", action="store_true", help="delete the drill's rows afterwards")
	return parser.parse_args()


if __name__ == "__main__":
	raise SystemExit(main())
