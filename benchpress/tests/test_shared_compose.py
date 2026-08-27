# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""The shared-infrastructure compose file may not declare a relative bind mount.

`mariadb_manager._compose_cmd` runs `docker compose -f <this file>` from inside the backend
container, so a relative source resolves against a container path and reaches the host daemon
as an absolute path the host does not have. The daemon then creates a directory there and the
service starts on stock defaults, silently. Both services sat like that for months: the fix is
that every setting is now a `command:` flag, which a daemon that refuses one exits over.

The guard is the fault class, not the instance — it rejects any relative source, in either the
short `src:dst` form or the long `{type, source}` form.
"""

import unittest
from pathlib import Path

import yaml

import benchpress

COMPOSE_PATH = Path(benchpress.__file__).parent / "config" / "docker-compose.yml"

REASON = (
	"docker compose runs this file from inside the backend container, so the relative source "
	"{source!r} reaches the host daemon as a container path the host does not have. Pass the "
	"setting as a command flag, or use a named volume."
)


class TestSharedCompose(unittest.TestCase):
	def test_no_service_declares_a_relative_bind(self):
		for service, source in _bind_sources(yaml.safe_load(COMPOSE_PATH.read_text())):
			with self.subTest(service=service, source=source):
				self.assertFalse(source.startswith("."), REASON.format(source=source))

	def test_the_guard_can_fail(self):
		"""A check that cannot fail is not a guard, and the real file can only ever pass now."""
		offender = {
			"services": {
				"mariadb": {
					"volumes": [
						"mariadb-data:/var/lib/mysql",
						"./mariadb.cnf:/etc/mysql/conf.d/benchpress.cnf:ro",
					]
				},
				"redis": {
					"volumes": [
						{
							"type": "bind",
							"source": "../redis.conf",
							"target": "/usr/local/etc/redis/redis.conf",
						}
					]
				},
			}
		}
		relative = [source for _, source in _bind_sources(offender) if source.startswith(".")]
		self.assertEqual(relative, ["./mariadb.cnf", "../redis.conf"])


def _bind_sources(compose: dict) -> list[tuple[str, str]]:
	"""Every (service, source) pair, reading both the short `src:dst` and long `{source:}` forms."""
	pairs = []
	for service, definition in compose["services"].items():
		for volume in definition.get("volumes", []):
			source = volume["source"] if isinstance(volume, dict) else volume.split(":")[0]
			pairs.append((service, source))
	return pairs
