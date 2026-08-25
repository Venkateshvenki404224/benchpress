#!/usr/bin/env python3
"""Fill a scratch Docker bridge until the daemon refuses, and report the number it refused at.

The harness for `specs/.../density-kernel-limits`. It answers one question the control plane
can only guess at: how many endpoints a bridge of a given prefix length really takes. Nothing
here reimplements the app's arithmetic — the daemon is the arbiter, exactly as it is in
`docker_manager.start_bench_container`.

Three properties make it safe to run against a host serving real tenants:

- **It fills a network it made, never a live one.** The target is always `bpdrill-<n>`, and
  the name is asserted before the first create. A drill that filled `benchpress-0` would take
  every bench on it offline at the moment the run believed it was measuring capacity.
- **It cleans up in a `finally`,** removing every container it created and then the network,
  and the run ends by asserting `docker network inspect` no longer finds it.
- **It refuses to run against the wrong site.** `--i-know-this-is` must match the site's own
  `base_domain`, read back from the control plane rather than from a file on this host.

The address is allocated at *start*, not at create (measured on Docker 29.7.2), so the drill
starts every endpoint. `--endpoints` caps the run: a /20 is 4094 addresses and this box has
2 vCPU and 7 GB, so the full-subnet run is opt-in and the default is small.

    python3 scripts/density_drill.py --subnet-size 24 --i-know-this-is benchpress.cloud
    python3 scripts/density_drill.py --subnet-size 20 --endpoints 4200 --i-know-this-is benchpress.cloud
"""

import argparse
import json
import os
import subprocess
import sys

SITE = os.environ.get("BENCHPRESS_SITE", "frontend")
COMPOSE_DIR = os.environ.get("BENCHPRESS_COMPOSE_DIR", "/home/ubuntu/benchpress_devops")

# Never a bench bridge. `_assert_scratch_network` is the guard; this is only the default.
NETWORK_PREFIX = "bpdrill-"
CONTAINER_PREFIX = "bpdrill-endpoint-"
IMAGE = "busybox:latest"
# 10.99 is unrouted here: the host carries 172.17, 172.27, 172.28, 172.30 and 172.31, and the
# bench family owns 10.20. Overlapping any of them would blackhole live traffic.
SUBNET_BASE = "10.99.0.0"

DOCKER_TIMEOUT = 120
BENCH_TIMEOUT = 300

EXHAUSTED = "no available ipv4 addresses"


def main() -> int:
	args = _parse_args()
	_assert_scratch_network(args.network)
	_assert_right_site(args.i_know_this_is)

	subnet = f"{SUBNET_BASE}/{args.subnet_size}"
	usable = 2 ** (32 - args.subnet_size) - 3  # network, broadcast, gateway
	print(f"drilling {args.network} on {subnet} — {usable} usable addresses, capped at {args.endpoints}")

	created = []
	try:
		_create_network(args.network, subnet)
		refused_at = _fill(args.network, args.endpoints, created)
		return _verdict(args, usable, refused_at, len(created))
	finally:
		_cleanup(args.network, created)


def _fill(network: str, cap: int, created: list[str]) -> int | None:
	"""Start endpoints until the daemon refuses; returns the attempt number it refused at."""
	for attempt in range(1, cap + 1):
		name = f"{CONTAINER_PREFIX}{attempt}"
		_docker("create", "--name", name, "--network", network, IMAGE, "sleep", "3600")
		created.append(name)
		failure = _docker("start", name, allow_failure=True)
		if failure is None:
			if attempt % 50 == 0:
				print(f"  {attempt} endpoints up")
			continue
		if EXHAUSTED not in failure.lower():
			_refuse(f"the daemon refused endpoint {attempt} for another reason:\n{failure}")
		print(f"  refused at endpoint {attempt}")
		return attempt
	return None


def _verdict(args, usable: int, refused_at: int | None, attempted: int) -> int:
	if refused_at is None:
		print(f"/{args.subnet_size}: {attempted} endpoints up, no refusal — the cap of {args.endpoints} was hit first")
		return 0
	held = refused_at - 1
	print(f"/{args.subnet_size}: {held} endpoints held, refused at {refused_at}, {usable} addresses usable")
	if held != usable:
		# Not a failure: infrastructure and any earlier tenant hold addresses too. It is the
		# number worth reading, so it is stated rather than folded into a pass.
		print(f"note: {usable - held} addresses were not reachable by this run")
	return 0


def _create_network(network: str, subnet: str) -> None:
	_docker("network", "create", "--driver", "bridge", "--subnet", subnet, network)


def _cleanup(network: str, created: list[str]) -> None:
	"""Remove everything this run made, then prove the scratch network is gone."""
	for name in created:
		_docker("rm", "-f", name, allow_failure=True)
	_docker("network", "rm", network, allow_failure=True)
	if _docker("network", "inspect", network, allow_failure=True) is None:
		_refuse(f"{network} still exists after cleanup — remove it by hand before drilling again")
	print(f"cleaned up: {len(created)} containers and {network}")


def _assert_scratch_network(network: str) -> None:
	if not network.startswith(NETWORK_PREFIX):
		_refuse(f"{network!r} is not a scratch network — the name must start with {NETWORK_PREFIX!r}")


def _assert_right_site(claimed: str) -> None:
	base_domain = _base_domain()
	if claimed != base_domain:
		_refuse(f"this site is {base_domain!r}, not {claimed!r}")


def _base_domain() -> str:
	"""The site's own `base_domain`, read through bench rather than off this host's disk."""
	finished = subprocess.run(
		[
			"docker", "compose", "exec", "-T", "backend",
			"bench", "--site", SITE, "execute", "frappe.client.get_value",
			"--kwargs", json.dumps({"doctype": "BenchPress Settings", "fieldname": "base_domain"}),
		],
		cwd=COMPOSE_DIR,
		capture_output=True,
		text=True,
		# Closed deliberately: `docker compose exec` under a timeout hangs forever if it
		# inherits a terminal it can read from.
		stdin=subprocess.DEVNULL,
		timeout=BENCH_TIMEOUT,
	)
	if finished.returncode:
		_refuse(f"could not read base_domain:\n{finished.stdout}\n{finished.stderr}")
	for line in reversed(finished.stdout.splitlines()):
		if "base_domain" in line:
			return line.split("base_domain")[-1].strip(" ':\"},")
	_refuse(f"bench printed no base_domain:\n{finished.stdout}")


def _docker(*arguments: str, allow_failure: bool = False) -> str | None:
	"""Run one docker command; returns None on success and stderr on an allowed failure."""
	finished = subprocess.run(
		["docker", *arguments],
		capture_output=True,
		text=True,
		stdin=subprocess.DEVNULL,
		timeout=DOCKER_TIMEOUT,
	)
	if not finished.returncode:
		return None
	if allow_failure:
		return finished.stderr or finished.stdout
	_refuse(f"docker {' '.join(arguments)} failed:\n{finished.stderr}")


def _refuse(reason: str) -> None:
	print(f"refusing to run: {reason}", file=sys.stderr)
	raise SystemExit(2)


def _parse_args():
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--network", default="bpdrill-0", help="scratch network name; must be bpdrill-*")
	parser.add_argument("--subnet-size", type=int, default=24, help="prefix length of the scratch subnet")
	parser.add_argument("--endpoints", type=int, default=60, help="stop after this many, refusal or not")
	parser.add_argument("--i-know-this-is", required=True, help="the site's base_domain")
	return parser.parse_args()


if __name__ == "__main__":
	raise SystemExit(main())
