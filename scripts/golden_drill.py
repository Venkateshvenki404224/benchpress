#!/usr/bin/env python3
"""Deploy the same lab with its golden and without it, and print what each arm cost.

The harness for `specs/.../golden-bench-images`. It never reimplements the claim: every deploy
goes over HTTP to the shipped `create_bench` endpoint, and every duration is read back out of
the run's own Deploy Log, which is where the numbers in the spec came from.

Three properties make it safe to run against a host that is serving real tenants:

- **It goes to the host's own nginx, not through the CDN.** The public name is behind
  Cloudflare, which answers a machine client with `1010` rather than with the endpoint.
  `BENCHPRESS_URL` overrides it.
- **It refuses to run against the wrong site.** `--i-know-this-is` must match the site's own
  `base_domain`, and the drill token must authenticate as the user the setup step just made.
- **It only ever touches what it created.** Every bench belongs to `golden-drill@example.com`,
  a user only `benchpress.golden_drill` mints, and cleanup runs in a `finally` — never on
  status, never on a lab it did not drill.

`--cold` is the control, and it is the same image: it turns `restore_from_golden` off for the
run and puts it back afterwards, so both arms deploy the same lab, the same apps and the same
container on the same host, differing only in whether the site is restored or created.

Runs are sequential and re-deploy one bench, because `get_instance_id` is `md5(email + lab)`
and one user against one lab is one bench however many times it is asked for. A redeploy drops
the site database and recreates the container first, so each run's site step is a fresh one.

    python3 scripts/golden_drill.py --lab crm --runs 3 --i-know-this-is benchpress.cloud
    python3 scripts/golden_drill.py --lab crm --runs 3 --cold --i-know-this-is benchpress.cloud
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

SITE = os.environ.get("BENCHPRESS_SITE", "frontend")
COMPOSE_DIR = os.environ.get("BENCHPRESS_COMPOSE_DIR", "/home/ubuntu/benchpress_devops")
BASE_URL = os.environ.get("BENCHPRESS_URL", "http://127.0.0.1:8080")
# nginx routes by `FRAPPE_SITE_NAME_HEADER`, not by this, but a request that names the site it
# means is the one worth measuring.
HOST_HEADER = os.environ.get("BENCHPRESS_HOST", "staging.benchpress.cloud")

CREATE_BENCH = "/api/method/benchpress.api.create_bench"
GET_BENCHES = "/api/method/benchpress.api.get_benches"
LOGGED_USER = "/api/method/frappe.auth.get_logged_user"

REQUEST_TIMEOUT = 120
BENCH_TIMEOUT = 900
DEPLOY_TIMEOUT = 900
POLL_SECONDS = 5

TERMINAL = ("Running", "Failed", "Stopped")


def main() -> int:
	args = _parse_args()
	if args.mode == "cleanup":
		print("cleanup:", json.dumps(_bench_execute("cleanup")))
		return 0

	setup = _bench_execute("setup", lab=args.lab, cold=1 if args.cold else 0)
	# Inside the try: setup has already moved the site's golden switch, so every way out of here
	# has to put it back, including the refusal below.
	try:
		_assert_right_site(args.i_know_this_is, setup)
		return _report(args, setup, _run(args, setup))
	finally:
		print("restore:", json.dumps(_bench_execute("restore", restore_before=setup["restore_before"])))
		print("cleanup:", json.dumps(_bench_execute("cleanup")))


def _run(args, setup) -> list[dict]:
	"""One deploy per run, each waited out and measured before the next one starts."""
	results = []
	for index in range(1, args.runs + 1):
		started = time.monotonic()
		bench = _deploy(setup)
		if not bench:
			results.append({"run": index, "error": "create_bench was refused"})
			continue
		status = _wait_for_deploy(setup, bench)
		measured = _bench_execute("measure", bench=bench)
		results.append(
			{
				"run": index,
				"bench": bench,
				"status": status,
				"waited": round(time.monotonic() - started, 1),
				**measured,
			}
		)
		print(
			f"  run {index}: {status} · site {measured.get('site_seconds')}s"
			f" · restored {measured.get('restored')}"
		)
	return results


def _deploy(setup) -> str | None:
	payload = {"lab": setup["lab"], "site_name": setup["site_label"]}
	body = _post(CREATE_BENCH, payload, setup)
	return (body or {}).get("message", {}).get("name")


def _wait_for_deploy(setup, bench: str) -> str:
	"""Poll the shipped bench list until this bench stops deploying."""
	deadline = time.monotonic() + DEPLOY_TIMEOUT
	status = "Deploying"
	while time.monotonic() < deadline:
		time.sleep(POLL_SECONDS)
		rows = (_get(GET_BENCHES, setup) or {}).get("message") or []
		status = next((row.get("status") for row in rows if row.get("name") == bench), status)
		if status in TERMINAL:
			return status
	return f"still {status} after {DEPLOY_TIMEOUT}s"


def _report(args, setup, results: list[dict]) -> int:
	"""One table, and every run this drill could not use printed rather than dropped."""
	mode = "golden" if setup["restoring"] else "cold"
	usable = [r for r in results if r.get("site_seconds") is not None and r.get("status") == "Running"]
	measured_runs = {r["run"] for r in usable}
	dropped = [r for r in results if r["run"] not in measured_runs]

	print(f"\n{'lab':<16} {'mode':<8} {'n':>3} {'p50':>8} {'p95':>8} {'total p50':>10}")
	if usable:
		site = sorted(r["site_seconds"] for r in usable)
		total = sorted(r["total_seconds"] or 0.0 for r in usable)
		print(
			f"{args.lab:<16} {mode:<8} {len(usable):>3} {_percentile(site, 50):>8.1f} "
			f"{_percentile(site, 95):>8.1f} {_percentile(total, 50):>10.1f}"
		)
	else:
		print(f"{args.lab:<16} {mode:<8} {0:>3} {'-':>8} {'-':>8} {'-':>10}")

	restored = {r.get("restored") for r in usable}
	if usable and restored != {setup["restoring"]}:
		print(f"note: this run asked for {mode} and the logs report restored={restored}", file=sys.stderr)
	for run in dropped:
		print(f"dropped run {run['run']}: {json.dumps(run)}", file=sys.stderr)
	return 1 if not usable else 0


def _percentile(ordered: list[float], percent: int) -> float:
	"""Nearest-rank, because a drill of three runs has no business interpolating."""
	rank = max(1, -(-len(ordered) * percent // 100))
	return ordered[rank - 1]


def _assert_right_site(claimed: str, setup: dict) -> None:
	if claimed != setup["base_domain"]:
		_refuse(f"this site is {setup['base_domain']!r}, not {claimed!r}")
	logged_in = (_get(LOGGED_USER, setup) or {}).get("message")
	if logged_in != setup["user"]:
		_refuse(f"{BASE_URL} authenticated the drill token as {logged_in!r}, not {setup['user']!r}")


def _auth(setup: dict) -> dict:
	return {
		"Authorization": f"token {setup['api_key']}:{setup['api_secret']}",
		"Host": HOST_HEADER,
	}


def _get(path: str, setup: dict) -> dict | None:
	return _send(urllib.request.Request(BASE_URL + path, headers=_auth(setup)))


def _post(path: str, payload: dict, setup: dict) -> dict | None:
	return _send(
		urllib.request.Request(
			BASE_URL + path,
			data=json.dumps({"data": json.dumps(payload)}).encode(),
			headers={**_auth(setup), "Content-Type": "application/json"},
			method="POST",
		)
	)


def _send(request) -> dict | None:
	try:
		with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
			return json.loads(response.read())
	except urllib.error.HTTPError as refusal:
		detail = refusal.read().decode(errors="replace")[:300]
		print(f"{request.full_url} -> {refusal.code}: {detail}", file=sys.stderr)
	except Exception as failure:
		print(f"{request.full_url} -> {failure!r}", file=sys.stderr)
	return None


def _refuse(reason: str) -> None:
	print(f"refusing to run: {reason}", file=sys.stderr)
	raise SystemExit(2)


def _bench_execute(function: str, **kwargs) -> dict:
	"""Call one `benchpress.golden_drill` function inside the backend container.

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
		f"benchpress.golden_drill.{function}",
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
		_refuse(f"golden_drill.{function} failed:\n{finished.stdout}\n{finished.stderr}")
	return _last_json(finished.stdout, function)


def _last_json(output: str, function: str) -> dict:
	for line in reversed(output.splitlines()):
		try:
			parsed = json.loads(line)
		except ValueError:
			continue
		if isinstance(parsed, dict):
			return parsed
	_refuse(f"golden_drill.{function} printed nothing that parses:\n{output}")


def _parse_args():
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--mode", choices=("drill", "cleanup"), default="drill")
	parser.add_argument("--lab", default="crm", help="the lab to drill, which must already be built")
	parser.add_argument("--runs", type=int, default=3)
	parser.add_argument("--cold", action="store_true", help="the control: same image, no golden")
	parser.add_argument("--i-know-this-is", required=True, help="the site's base_domain")
	return parser.parse_args()


if __name__ == "__main__":
	raise SystemExit(main())
