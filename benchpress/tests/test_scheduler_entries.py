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

import frappe

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


class TestJobPathsResolve(unittest.TestCase):
	"""Frappe resolves a job from a dotted string at run time, so a move that breaks one is silent.

	A `Scheduled Job Type` row is the worst carrier: `ScheduledJobType.execute()` swallows the
	import error, writes no log row and still advances `last_execution`.
	"""

	def test_every_scheduled_method_resolves(self):
		for method in _scheduled_methods():
			with self.subTest(method=method):
				frappe.get_attr(method)

	def test_every_enqueue_target_resolves(self):
		for module, target in _enqueue_targets():
			with self.subTest(module=module, target=target):
				frappe.get_attr(target)

	def test_the_walker_finds_the_targets(self):
		"""A walker that matched nothing would pass the test above for the wrong reason."""
		targets = {target for _, target in _enqueue_targets()}
		self.assertIn("benchpress.lifecycle.deploy_bench", targets)
		self.assertGreater(len(targets), 8)


def _scheduled_methods() -> list[str]:
	"""Flatten `scheduler_events` — frequency lists, plus the cron dict of lists."""
	methods = []
	for frequency in scheduler_events.values():
		entries = frequency.values() if isinstance(frequency, dict) else [frequency]
		for entry in entries:
			methods.extend(entry)
	return methods


def _enqueue_targets() -> list[tuple[str, str]]:
	"""Every literal first argument of a `frappe.enqueue` call outside the test package.

	A target built at run time is skipped rather than failed — `image_cache` passes one
	through a variable, and no static walk can say what it holds.
	"""
	package = Path(__file__).resolve().parent.parent
	targets = []
	for path in sorted(package.rglob("*.py")):
		if path.parent.name == "tests":
			continue
		for node in ast.walk(ast.parse(path.read_text())):
			target = _enqueue_target(node)
			if target:
				targets.append((str(path.relative_to(package)), target))
	return targets


def _enqueue_target(node: ast.AST) -> str | None:
	if not isinstance(node, ast.Call) or getattr(node.func, "attr", None) != "enqueue":
		return None
	method = next((kw.value for kw in node.keywords if kw.arg == "method"), None)
	if node.args:
		method = node.args[0]
	return method.value if isinstance(method, ast.Constant) and isinstance(method.value, str) else None


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
