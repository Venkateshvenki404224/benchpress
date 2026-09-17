#!/usr/bin/env python3
"""Deploy a lab N at a time, with its golden or without it, and print what each deploy cost.

python3 scripts/golden_drill.py --lab crm --concurrent 5 --probe-login --i-know-this-is benchpress.cloud
"""

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from drill_probes import MemorySampler, host_line, seconds_to_login

SITE = os.environ.get("BENCHPRESS_SITE", "frontend")
COMPOSE_DIR = os.environ.get("BENCHPRESS_COMPOSE_DIR", "/home/ubuntu/benchpress_devops")
BASE_URL = os.environ.get("BENCHPRESS_URL", "http://127.0.0.1:8080")
# nginx routes by `FRAPPE_SITE_NAME_HEADER`, not by this, but a request that names the site it
# means is the one worth measuring.
HOST_HEADER = os.environ.get("BENCHPRESS_HOST", "staging.benchpress.cloud")

CREATE_BENCH = "/api/method/benchpress.api.create_bench"
GET_BENCHES = "/api/method/benchpress.api.get_benches"
GET_CREDENTIALS = "/api/method/benchpress.api.get_bench_credentials"
LOGGED_USER = "/api/method/frappe.auth.get_logged_user"
SITE_HTTP_PORT = 8000

REQUEST_TIMEOUT = 120
BENCH_TIMEOUT = 900
DEPLOY_TIMEOUT = 900
POLL_SECONDS = 2

TERMINAL = ("Running", "Error", "Failed", "Stopped")
COLUMNS = ("run", "status", "site_seconds", "total_seconds", "login_seconds", "restored", "peak_mem_mb")
MEDIAN_OF = ("site_seconds", "total_seconds", "login_seconds", "peak_mem_mb")


def main() -> int:
	args = _parse_args()
	if args.mode == "cleanup":
		print("cleanup:", json.dumps(_bench_execute("cleanup")))
		return 0

	setup = _bench_execute("setup", {"lab": args.lab, "cold": int(args.cold), "concurrent": args.concurrent})
	# Inside the try: setup has already moved the site's golden switch, so every way out of here
	# has to put it back, including the refusal below.
	try:
		_assert_right_site(args.i_know_this_is, setup)
		print(host_line())
		return _report(args, setup, _run(args, setup))
	finally:
		print("restore:", json.dumps(_bench_execute("restore", {"restore_before": setup["restore_before"]})))
		print("cleanup:", json.dumps(_bench_execute("cleanup")))


def _run(args, setup) -> list[dict]:
	"""`--runs` rounds. Each starts one deploy per drill user at once and waits all of them out."""
	results = []
	for index in range(1, args.runs + 1):
		with MemorySampler() as memory, ThreadPoolExecutor(max_workers=len(setup["users"])) as pool:
			rows = list(pool.map(lambda user: _one_deploy(args, setup, user, memory), setup["users"]))
		for n, row in enumerate(rows, start=1):
			results.append({"run": f"{index}.{n}", **row})
			print(f"  run {index}.{n}: {row.get('status') or row.get('error')}")
	return results


def _one_deploy(args, setup: dict, user: dict, memory: MemorySampler) -> dict:
	"""One deploy, from its `create_bench` call to its measurement, through a login when asked."""
	started = time.monotonic()
	bench = _deploy(setup["lab"], user)
	if not bench:
		return {"error": "create_bench was refused"}
	row = _wait_for_deploy(user, bench)
	result = {"bench": bench, "status": row.get("status")}
	if args.probe_login and row.get("status") == "Running":
		result["login_seconds"] = _probe_login(user, row, started)
	result["peak_mem_mb"] = memory.peak_since(started)
	result["measured"] = _bench_execute("measure", {"bench": bench}, allow_empty=True)
	return result


def _deploy(lab: str, user: dict) -> str | None:
	payload = {"lab": lab, "site_name": user["site_label"]}
	body = _post(CREATE_BENCH, payload, user)
	return (body or {}).get("message", {}).get("name")


def _wait_for_deploy(user: dict, bench: str) -> dict:
	"""Poll the shipped bench list until this bench stops deploying, and return its row."""
	deadline = time.monotonic() + DEPLOY_TIMEOUT
	row = {"name": bench, "status": "Deploying"}
	while time.monotonic() < deadline:
		time.sleep(POLL_SECONDS)
		rows = (_get(GET_BENCHES, user) or {}).get("message") or []
		row = next((candidate for candidate in rows if candidate.get("name") == bench), row)
		if row.get("status") in TERMINAL:
			return row
	return {**row, "status": f"still {row.get('status')} after {DEPLOY_TIMEOUT}s"}


def _probe_login(user: dict, row: dict, started: float) -> float | None:
	"""The new site's own Administrator login, at its public address or else its container address."""
	query = urllib.parse.urlencode({"bench_name": row["name"]})
	password = ((_get(f"{GET_CREDENTIALS}?{query}", user) or {}).get("message") or {}).get("admin_password")
	container = row.get("container_ip") and f"http://{row['container_ip']}:{SITE_HTTP_PORT}"
	address = row.get("public_url") or container
	if not (password and address):
		print(f"login probe skipped for {row['name']}: no password or no address", file=sys.stderr)
		return None
	return seconds_to_login(address, password, started)


def _report(args, setup, results: list[dict]) -> int:
	"""One row per deploy, then a median row. A run with no measurement says so and is not guessed."""
	mode = "golden" if setup["restoring"] else "cold"
	print(f"\n{args.lab} · {mode} · {args.concurrent} at once")
	print(_table_row(COLUMNS))
	usable = []
	for result in results:
		measured = result.get("measured")
		if not measured or result.get("status") != "Running":
			print(f"{result['run']:<8} {result.get('status') or result.get('error')!s:<10} no measurement")
			print(f"dropped run {result['run']}: {json.dumps(result)}", file=sys.stderr)
			continue
		row = {**result, **measured}
		usable.append(row)
		print(_table_row([row.get(column) for column in COLUMNS]))
	if usable:
		print(_table_row(["median", "", *[_median(usable, column) for column in COLUMNS[2:]]]))

	restored = {row.get("restored") for row in usable}
	if usable and restored != {setup["restoring"]}:
		print(f"note: this run asked for {mode} and the logs report restored={restored}", file=sys.stderr)
	for row in usable:
		if row.get("site_timings"):
			print(f"  run {row['run']} site step: {row['site_timings']}")
	return 0 if usable else 1


def _median(rows: list[dict], column: str):
	if column not in MEDIAN_OF:
		return ""
	values = [row[column] for row in rows if row.get(column) is not None]
	return round(statistics.median(values), 1) if values else None


def _table_row(cells) -> str:
	shown = ["-" if cell is None else str(cell) for cell in cells]
	return f"{shown[0]:<8} {shown[1]:<10} " + " ".join(f"{cell:>13}" for cell in shown[2:])


def _assert_right_site(claimed: str, setup: dict) -> None:
	if claimed != setup["base_domain"]:
		_refuse(f"this site is {setup['base_domain']!r}, not {claimed!r}")
	for user in setup["users"]:
		logged_in = (_get(LOGGED_USER, user) or {}).get("message")
		if logged_in != user["user"]:
			_refuse(f"{BASE_URL} authenticated the drill token as {logged_in!r}, not {user['user']!r}")


def _auth(user: dict) -> dict:
	return {
		"Authorization": f"token {user['api_key']}:{user['api_secret']}",
		"Host": HOST_HEADER,
	}


def _get(path: str, user: dict) -> dict | None:
	return _send(urllib.request.Request(BASE_URL + path, headers=_auth(user)))


def _post(path: str, payload: dict, user: dict) -> dict | None:
	return _send(
		urllib.request.Request(
			BASE_URL + path,
			data=json.dumps({"data": json.dumps(payload)}).encode(),
			headers={**_auth(user), "Content-Type": "application/json"},
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


def _bench_execute(function: str, kwargs: dict | None = None, *, allow_empty: bool = False) -> dict | None:
	"""Call one `benchpress.golden_drill` function inside the backend container.

	`stdin` is closed: `docker compose exec` under a timeout hangs if it inherits a terminal.
	"""
	command = ["docker", "compose", "exec", "-T", "backend", "bench", "--site", SITE, "execute"]
	command.append(f"benchpress.golden_drill.{function}")
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
	return _last_json(finished.stdout, function, allow_empty)


def _last_json(output: str, function: str, allow_empty: bool) -> dict | None:
	"""The last JSON object `bench execute` printed. It prints nothing for a function that returned None."""
	for line in reversed(output.splitlines()):
		try:
			parsed = json.loads(line)
		except ValueError:
			continue
		if isinstance(parsed, dict):
			return parsed
	if allow_empty:
		return None
	_refuse(f"golden_drill.{function} printed nothing that parses:\n{output}")


def _parse_args():
	parser = argparse.ArgumentParser(
		description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
	)
	parser.add_argument("--mode", choices=("drill", "cleanup"), default="drill")
	parser.add_argument("--lab", default="crm", help="the lab to drill, which must already be built")
	parser.add_argument("--runs", type=int, default=3)
	parser.add_argument(
		"--concurrent", type=int, default=1, help="deploys started at once, one per drill user"
	)
	parser.add_argument("--cold", action="store_true", help="the control: same image, no golden")
	parser.add_argument(
		"--probe-login", action="store_true", help="time each deploy to the first login its site accepts"
	)
	parser.add_argument("--i-know-this-is", required=True, help="the site's base_domain")
	args = parser.parse_args()
	if args.concurrent < 1:
		parser.error("--concurrent must be at least 1")
	return args


if __name__ == "__main__":
	raise SystemExit(main())
