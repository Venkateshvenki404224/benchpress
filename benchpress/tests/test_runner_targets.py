# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""What an unattended loop is told to run against, and what it is told to sign in with.

`frontend` is the deployment's own site. It carries no `allow_tests`, so `run-tests` refuses
it — but only after disabling its scheduler from a value the runner holds in memory and
restores on a clean exit. A site with the scheduler off composes mail and never sends it,
silently. An interrupted iteration is normal in a loop, so the refusal is the likely outcome,
not the exceptional one. The instructions are read fresh every iteration, which is why a scan
of them is the test.

Each pattern needs whitespace or a line start before `--site`, so the prose that forbids the
command — which writes it inside backticks — does not read as the command itself.
"""

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# `scripts/ralph.sh` cd's here before invoking `claude`, so CLAUDE.md is loaded every
# iteration alongside the prompt. It is a runner file, whatever else it is.
CLAUDE_MD = "CLAUDE.md"

# The loop's own instructions, and the two templates that generate them.
LOOP_FILES = (
	"scripts/prompt.md",
	"scripts/ralph.sh",
	".claude/skills/issue-to-phases/SKILL.md",
	".claude/skills/issue-to-phases/assets/prompt.md.template",
	".claude/skills/issue-to-phases/assets/ralph.sh.template",
	".claude/skills/issue-to-phases/references/ralph-loop.md",
)

# What a person reads before typing a command. `docs/reference/cli-and-scripts.mdx` is
# published, so a self-hoster runs what it prints.
DOC_FILES = (
	CLAUDE_MD,
	"docs/reference/cli-and-scripts.mdx",
	"README.md",
	"CONTRIBUTING.md",
)

ON_FRONTEND = r"""(?:^|\s)--site[= ]["']?frontend\b"""

# `run-parallel-tests` and `run-ui-tests` disable the scheduler the same way `run-tests` does.
ANY_TEST_COMMAND = r".*\brun-[\w-]*tests\b"

# Testing the deployment site is wrong everywhere. Migrating it is what a person does on
# deploy, so only the loop is forbidden to name it.
RUN_TESTS_ON_FRONTEND = re.compile(ON_FRONTEND + ANY_TEST_COMMAND)
BENCH_ON_FRONTEND = re.compile(ON_FRONTEND)

# Any value for either name, except the empty `${BP_TEST_URL:-}` the guard reads with.
CREDENTIAL_DEFAULT = re.compile(r"\b(BP_TEST_URL|BP_TEST_PASSWORD)=(?!\$\{\1:-\}|\s|$)")


def _missing(names: tuple[str, ...]) -> list[str]:
	return [name for name in names if not (REPO / name).exists()]


def _commands(text: str) -> list[tuple[int, str]]:
	"""A command wrapped over a backslash is one line to a shell, so it is one line here."""
	lines = []
	for number, line in enumerate(text.splitlines(), 1):
		if lines and lines[-1][1].endswith("\\"):
			start, held = lines[-1]
			lines[-1] = (start, f"{held[:-1]} {line.strip()}")
		else:
			lines.append((number, line))
	return lines


def _hits(pattern: re.Pattern, names: tuple[str, ...]) -> list[str]:
	found = []
	for name in names:
		path = REPO / name
		if not path.exists():
			continue
		for number, line in _commands(path.read_text(encoding="utf-8")):
			if pattern.search(line):
				found.append(f"{name}:{number}: {line.strip()}")
	return found


class TestRunnerTargets(unittest.TestCase):
	def test_every_runner_file_is_where_the_scan_looks(self):
		"""A renamed file would make every other assertion here vacuous."""
		self.assertEqual(_missing((*LOOP_FILES, *DOC_FILES)), [])

	def test_no_runner_instruction_names_the_deployment_site(self):
		self.assertEqual(_hits(BENCH_ON_FRONTEND, LOOP_FILES), [], "a loop is pointed at `frontend`")

	def test_nothing_an_agent_reads_tests_the_deployment_site(self):
		self.assertEqual(_hits(RUN_TESTS_ON_FRONTEND, (*LOOP_FILES, *DOC_FILES)), [])

	def test_the_loop_names_the_test_site_for_both_commands(self):
		"""`assertIn` would print the whole prompt into a log a loop has to read."""
		prompt = (REPO / "scripts/prompt.md").read_text(encoding="utf-8")
		for command in ("run-tests", "migrate"):
			self.assertTrue(
				f"--site bp_test_site {command}" in prompt,
				f"scripts/prompt.md names no test site for `{command}`",
			)

	def test_every_template_still_names_a_site_to_migrate(self):
		"""Losing the site name outright would pass every pattern above."""
		for name in LOOP_FILES:
			body = (REPO / name).read_text(encoding="utf-8")
			if "migrate" in body:
				self.assertIn("--site bp_test_site migrate", body, f"{name} migrates a nameless site")

	def test_the_browser_credentials_carry_no_default(self):
		self.assertEqual(
			_hits(CREDENTIAL_DEFAULT, LOOP_FILES), [], "a browser credential still has a default"
		)
