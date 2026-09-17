"""What `scripts/golden_drill.py` measures outside the Deploy Log: the first login, memory, and the host.

Standard library only, like the drill, because it runs on the host rather than in a bench.
"""

import http.client
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.parse

EDGE = os.environ.get("BENCHPRESS_EDGE", "127.0.0.1:8443")

LOGIN = "/api/method/login"
LOGIN_POLL_SECONDS = 2
LOGIN_TIMEOUT = 120
LOGIN_REQUEST_TIMEOUT = 10
MEMORY_POLL_SECONDS = 5
STATS_TIMEOUT = 120
BYTES_PER_UNIT = {"B": 1, "KiB": 2**10, "MiB": 2**20, "GiB": 2**30, "kB": 10**3, "MB": 10**6, "GB": 10**9}


def host_line() -> str:
	"""`free -b` totals, the swap in use and `nproc`, so a number is never read against another host."""
	free = {line.split()[0]: line.split() for line in _output(["free", "-b"]).splitlines()[1:]}
	memory, swap = free["Mem:"], free["Swap:"]
	return (
		f"host: {_gib(memory[1])} GiB RAM, {_gib(memory[6])} GiB available, "
		f"swap {_gib(swap[2])} of {_gib(swap[1])} GiB in use, {_output(['nproc']).strip()} CPUs"
	)


def seconds_to_login(address: str, password: str, started: float) -> float | None:
	"""Seconds from `started` to the first login the site accepts, trying every 2 s. None past the cap."""
	deadline = time.monotonic() + LOGIN_TIMEOUT
	while time.monotonic() < deadline:
		if _logged_in(address, password):
			return round(time.monotonic() - started, 1)
		time.sleep(LOGIN_POLL_SECONDS)
	print(f"login probe gave up on {address} after {LOGIN_TIMEOUT}s (edge {EDGE})", file=sys.stderr)
	return None


class MemorySampler:
	"""Every container's memory, summed from `docker stats`, sampled while one round of deploys runs."""

	def __init__(self):
		self.samples = []
		self._stop = threading.Event()
		self._thread = threading.Thread(target=self._sample, daemon=True)

	def __enter__(self):
		self._thread.start()
		return self

	def __exit__(self, *exc):
		self._stop.set()
		self._thread.join()

	def peak_since(self, started: float) -> int | None:
		window = [mebibytes for at, mebibytes in list(self.samples) if at >= started]
		return round(max(window)) if window else None

	def _sample(self):
		while not self._stop.is_set():
			at = time.monotonic()
			total = _containers_memory_mib()
			if total is not None:
				self.samples.append((at, total))
			self._stop.wait(MEMORY_POLL_SECONDS)


class EdgeConnection(http.client.HTTPSConnection):
	"""HTTPS to the host's own Traefik that presents the public name, for SNI and for `Host`."""

	def __init__(self, hostname: str, edge: str):
		super().__init__(hostname, timeout=LOGIN_REQUEST_TIMEOUT)
		address, _, port = edge.rpartition(":")
		self.edge = (address, int(port))

	def connect(self):
		self.sock = self._context.wrap_socket(
			socket.create_connection(self.edge, self.timeout), server_hostname=self.host
		)


def _logged_in(address: str, password: str) -> bool:
	"""One login attempt. A refusal and an unreachable site are both only a reason to try again."""
	parts = urllib.parse.urlsplit(address)
	connection = (
		EdgeConnection(parts.hostname, EDGE)
		if parts.scheme == "https"
		else http.client.HTTPConnection(parts.hostname, parts.port or 80, timeout=LOGIN_REQUEST_TIMEOUT)
	)
	try:
		connection.request(
			"POST",
			LOGIN,
			body=urllib.parse.urlencode({"usr": "Administrator", "pwd": password}),
			headers={"Content-Type": "application/x-www-form-urlencoded"},
		)
		response = connection.getresponse()
		return response.status == 200 and json.loads(response.read()).get("message") == "Logged In"
	except (OSError, ValueError, http.client.HTTPException):
		return False
	finally:
		connection.close()


def _containers_memory_mib() -> float | None:
	finished = subprocess.run(
		["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}"],
		capture_output=True,
		text=True,
		stdin=subprocess.DEVNULL,
		timeout=STATS_TIMEOUT,
	)
	if finished.returncode:
		return None
	return sum(_bytes(line.split("/")[0]) for line in finished.stdout.splitlines()) / 2**20


def _bytes(size: str) -> float:
	"""`325.6MiB` as bytes. Anything unreadable counts as nothing rather than as a guess."""
	match = re.fullmatch(r"([\d.]+)\s*([A-Za-z]+)", size.strip())
	if not match or match[2] not in BYTES_PER_UNIT:
		return 0.0
	return float(match[1]) * BYTES_PER_UNIT[match[2]]


def _gib(size: str) -> str:
	return f"{int(size) / 2**30:.2f}"


def _output(command: list[str]) -> str:
	return subprocess.run(command, capture_output=True, text=True, check=True).stdout
