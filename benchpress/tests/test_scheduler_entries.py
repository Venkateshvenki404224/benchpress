# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""Every scheduled entry that can reach Docker must hand its work to a socket-mounted queue.

`ScheduledJobType.get_queue_name()` returns `long` only for a frequency string containing `Long`
or `Maintenance`, so every entry in `scheduler_events` is enqueued on `default` — which
`queue-long` (Docker socket mounted) and `queue-short` (no socket) both consume, and the idle
worker usually wins the race. Three entries sat broken for weeks because the only symptom is a
socket `FileNotFoundError` in an error log nobody reads. This is the guard; the rule it enforces
is written above `scheduler_events` in `hooks.py`.

Reachability follows module-level imports only, so a module that imports Docker inside a function
body is invisible here. That is the whole blind spot, and nothing under `scheduler_events` does it
today — `credits.reaper` is the one that imports `deploy_manager` lazily, and it enqueues anyway.
"""

import ast
import unittest
from importlib.util import find_spec
from pathlib import Path

from benchpress.hooks import scheduler_events

DOCKER_MODULE = "benchpress.docker_manager"
SOCKET_QUEUES = {"long", "stops"}


class TestSchedulerEntries(unittest.TestCase):
	def test_every_docker_reaching_entry_is_an_enqueuer(self):
		for method in _scheduled_methods():
			module, _, function = method.rpartition(".")
			if not _reaches_docker(module):
				continue
			with self.subTest(method=method):
				self.assertTrue(
					_enqueues_onto_socket_queue(module, function),
					f"{method} is scheduled from a module that reaches Docker, so it must call "
					f"frappe.enqueue(queue=…) onto one of {sorted(SOCKET_QUEUES)} instead of "
					"doing the work itself. See the rule above `scheduler_events` in hooks.py.",
				)

	def test_the_guard_can_fail(self):
		"""A check that cannot fail is not a guard: the two halves must each reject something."""
		self.assertTrue(_reaches_docker("benchpress.stats_collector"))
		self.assertFalse(_reaches_docker("benchpress.credits.admission_repair"))
		self.assertFalse(_enqueues_onto_socket_queue("benchpress.stats_collector", "collect_bench_stats"))


def _scheduled_methods() -> list[str]:
	"""Flatten `scheduler_events` — frequency lists, plus the cron dict of lists."""
	methods = []
	for frequency in scheduler_events.values():
		entries = frequency.values() if isinstance(frequency, dict) else [frequency]
		for entry in entries:
			methods.extend(entry)
	return methods


def _reaches_docker(module: str, seen: set[str] | None = None) -> bool:
	seen = set() if seen is None else seen
	if module in seen:
		return False
	seen.add(module)
	if module == DOCKER_MODULE:
		return True
	return any(_reaches_docker(imported, seen) for imported in _benchpress_imports(module))


def _benchpress_imports(module: str) -> list[str]:
	"""Module-level `benchpress` imports, both `from x import y` and `import x`.

	A `from benchpress import docker_manager` names the submodule in its aliases, not its module,
	so both are collected. Aliases that turn out to be functions simply resolve to nothing.
	"""
	imported = []
	for node in _parse(module).body:
		if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("benchpress"):
			imported.append(node.module)
			imported.extend(f"{node.module}.{alias.name}" for alias in node.names)
		elif isinstance(node, ast.Import):
			imported.extend(a.name for a in node.names if a.name.startswith("benchpress"))
	return imported


def _enqueues_onto_socket_queue(module: str, function: str) -> bool:
	definition = next(
		(node for node in _parse(module).body if isinstance(node, ast.FunctionDef) and node.name == function),
		None,
	)
	return bool(definition) and any(_is_socket_enqueue(node) for node in ast.walk(definition))


def _is_socket_enqueue(node: ast.AST) -> bool:
	if not isinstance(node, ast.Call) or getattr(node.func, "attr", None) != "enqueue":
		return False
	queue = next((kw.value for kw in node.keywords if kw.arg == "queue"), None)
	return isinstance(queue, ast.Constant) and queue.value in SOCKET_QUEUES


def _parse(module: str) -> ast.Module:
	"""Source of `module`, or an empty tree when the name is not an importable .py module."""
	try:
		spec = find_spec(module)
	except (ImportError, AttributeError, ValueError):
		return ast.parse("")
	if not spec or not spec.origin or not spec.origin.endswith(".py"):
		return ast.parse("")
	return ast.parse(Path(spec.origin).read_text())
