"""AST guard: claim()'s refusal branch must call _record_denial() as the
second-to-last statement and frappe.throw() as the last statement in its
`if` block, with nothing between them.

Why AST, not a live-bench test: admission.py's own docstring on
_record_denial says the explicit commit is "safe... because this is the
LAST thing claim() does on the refusal path" -- but nothing enforces that
at the call site itself (claim()), only documents it on the callee. A
future refactor could insert a statement between _record_denial(...) and
frappe.throw(...) inside claim()'s `if limit and ...:` block without
violating any existing test, since test_a_cap_refusal_writes_a_decision_envelope_before_the_throw
only asserts the row's content, not statement adjacency.

This check needs no live bench/DB -- it is pure source inspection, so it
runs standalone with plain python3 (confirmed working without a live
BenchPress install).
"""

import ast
import sys
from pathlib import Path

ADMISSION_PY = Path(__file__).parent / "admission.py"


def _find_claim_function(tree: ast.Module) -> ast.FunctionDef:
	for node in ast.walk(tree):
		if isinstance(node, ast.FunctionDef) and node.name == "claim":
			return node
	raise AssertionError("claim() function not found in admission.py")


def _find_refusal_if_block(claim_fn: ast.FunctionDef) -> list[ast.stmt]:
	"""Find the `if limit and ...:` block that holds the refusal path."""
	for node in ast.walk(claim_fn):
		if isinstance(node, ast.If):
			# Match the specific refusal branch: body must contain a call
			# to _record_denial somewhere.
			calls = [
				n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", None)
				for n in ast.walk(node)
				if isinstance(n, ast.Call)
			]
			if "_record_denial" in calls:
				return node.body
	raise AssertionError("No if-block calling _record_denial found inside claim()")


def _call_name(stmt: ast.stmt) -> str | None:
	if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
		return None
	func = stmt.value.func
	if isinstance(func, ast.Name):
		return func.id
	if isinstance(func, ast.Attribute):
		return func.attr
	return None


def test_record_denial_is_immediately_followed_by_throw() -> None:
	"""The refusal if-block's statements must end with
	[..., _record_denial(...), frappe.throw(...)] -- nothing between them.
	"""
	tree = ast.parse(ADMISSION_PY.read_text())
	claim_fn = _find_claim_function(tree)
	body = _find_refusal_if_block(claim_fn)

	names = [_call_name(s) for s in body]
	assert "_record_denial" in names, f"_record_denial not called in refusal block: {names}"

	idx = names.index("_record_denial")
	assert idx + 1 < len(body), (
		"_record_denial() is the LAST statement in the refusal block -- "
		"there is no throw after it, which means the refusal path no "
		"longer raises. This is a bug, not a guard failure."
	)
	next_name = names[idx + 1]
	assert next_name == "throw", (
		f"claim()'s refusal block has a statement between _record_denial() and the throw: "
		f"found {body[idx + 1]!r} (resolved call name: {next_name!r}). "
		"_record_denial()'s docstring says its explicit commit is safe only because "
		"it is the LAST thing claim() does before the throw on this path -- "
		"inserting anything between them (even something that looks safe) can "
		"reopen the race the lock exists to close. If this is intentional, update "
		"_record_denial()'s docstring to match the new call order before changing this guard."
	)
	assert idx + 2 == len(body), (
		f"Unexpected statement(s) after the throw in the refusal block: {body[idx + 2 :]!r}"
	)


if __name__ == "__main__":
	test_record_denial_is_immediately_followed_by_throw()
	print(
		"PASS: _record_denial() is immediately followed by the throw in claim()'s refusal branch, nothing in between."
	)
