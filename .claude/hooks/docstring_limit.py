#!/usr/bin/env python3
"""Block docstrings longer than two content lines in files Claude just wrote."""

import ast
import json
import os
import re
import subprocess
import sys

MAX_LINES = int(os.environ.get("CLAUDE_DOCSTRING_MAX_LINES", "2"))
PY_EXT = (".py",)
JS_EXT = (".js", ".jsx", ".ts", ".tsx", ".vue", ".mjs", ".cjs")
SKIP = ("/node_modules/", "/.git/", "/site-packages/", "/dist/", "/build/", "/.venv/")


def changed_lines(path):
	"""Line numbers touched since HEAD; None means treat every line as new."""
	directory = os.path.dirname(path) or "."
	try:
		tracked = subprocess.run(
			["git", "-C", directory, "ls-files", "--error-unmatch", path],
			capture_output=True,
		).returncode == 0
		if not tracked:
			return None
		diff = subprocess.run(
			["git", "-C", directory, "diff", "--unified=0", "HEAD", "--", path],
			capture_output=True,
			text=True,
		)
		if diff.returncode != 0:
			return None
	except (OSError, subprocess.SubprocessError):
		return None

	lines = set()
	for hunk in re.finditer(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@", diff.stdout, re.M):
		start = int(hunk.group(1))
		count = int(hunk.group(2) or 1)
		lines.update(range(start, start + count))
	return lines


def python_violations(source):
	try:
		tree = ast.parse(source)
	except SyntaxError:
		return []

	found = []
	for node in ast.walk(tree):
		if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
			continue
		body = getattr(node, "body", None)
		if not body:
			continue
		first = body[0]
		if not (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)):
			continue
		if not isinstance(first.value.value, str):
			continue
		content = [l for l in first.value.value.splitlines() if l.strip()]
		if len(content) > MAX_LINES:
			name = getattr(node, "name", "<module>")
			found.append((first.lineno, first.end_lineno, name, len(content)))
	return found


def jsdoc_violations(source):
	found = []
	for block in re.finditer(r"/\*\*.*?\*/", source, re.S):
		body = block.group(0)[3:-2]
		content = []
		for line in body.splitlines():
			line = line.strip().lstrip("*").strip()
			if line and not line.startswith("@"):
				content.append(line)
		if len(content) > MAX_LINES:
			start = source.count("\n", 0, block.start()) + 1
			end = source.count("\n", 0, block.end()) + 1
			found.append((start, end, "JSDoc block", len(content)))
	return found


def main():
	try:
		payload = json.load(sys.stdin)
	except (json.JSONDecodeError, ValueError):
		return

	response = payload.get("tool_response") or {}
	tool_input = payload.get("tool_input") or {}
	path = response.get("filePath") or tool_input.get("file_path")
	if not path or not os.path.isfile(path):
		return
	path = os.path.abspath(path)
	if any(part in path for part in SKIP):
		return

	if path.endswith(PY_EXT):
		check = python_violations
	elif path.endswith(JS_EXT):
		check = jsdoc_violations
	else:
		return

	try:
		source = open(path, encoding="utf-8").read()
	except (OSError, UnicodeDecodeError):
		return

	violations = check(source)
	if not violations:
		return

	touched = changed_lines(path)
	if touched is not None:
		violations = [v for v in violations if touched & set(range(v[0], v[1] + 1))]
	if not violations:
		return

	listing = "\n".join(
		f"  - {os.path.basename(path)}:{start} ({name}) — {count} lines"
		for start, _, name, count in violations
	)
	print(json.dumps({
		"decision": "block",
		"reason": (
			f"Docstring length rule: a docstring is at most {MAX_LINES} lines. "
			f"These exceed it:\n{listing}\n"
			"Trim each to what it does plus the one non-obvious constraint. "
			"Rationale, history, and measurements belong in the commit message, not the docstring."
		),
		"systemMessage": f"Docstring limit: {len(violations)} over {MAX_LINES} lines in {os.path.basename(path)}",
		"suppressOutput": True,
	}))


if __name__ == "__main__":
	main()
