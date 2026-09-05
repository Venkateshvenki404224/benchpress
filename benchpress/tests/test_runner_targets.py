# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""What an unattended loop is told to run against, and what it is told to sign in with.

`frontend` is the deployment's own site. It carries no `allow_tests`, so `run-tests` refuses
it — but only after disabling its scheduler from a value the runner holds in memory and
restores on a clean exit. A site with the scheduler off composes mail and never sends it,
silently. An interrupted iteration is normal in a loop, so the refusal is the likely outcome,
not the exceptional one. The instructions are read fresh every iteration, which is why a scan
of them is the test.

The prose in these files names `--site frontend` to forbid it; the patterns match a bench
invocation, so a prohibition reads as one.
"""

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Every file an unattended runner reads, and the two templates that generate them.
RUNNER_FILES = (
	"scripts/prompt.md",
	"scripts/ralph.sh",
	".claude/skills/issue-to-phases/SKILL.md",
	".claude/skills/issue-to-phases/assets/prompt.md.template",
	".claude/skills/issue-to-phases/assets/ralph.sh.template",
	".claude/skills/issue-to-phases/references/ralph-loop.md",
)

BENCH_ON_FRONTEND = re.compile(r"bench\s+--site\s+frontend\b")

# `${BP_TEST_URL:-https://...}` and `${BP_TEST_PASSWORD:-admin}`, but not the empty
# `${BP_TEST_URL:-}` the guard reads with.
CREDENTIAL_DEFAULT = re.compile(r"\$\{(BP_TEST_URL|BP_TEST_PASSWORD):[-=][^}]")


def _present() -> list[Path]:
	return [REPO / name for name in RUNNER_FILES if (REPO / name).exists()]


def _hits(pattern: re.Pattern) -> list[str]:
	found = []
	for path in _present():
		for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
			if pattern.search(line):
				found.append(f"{path.relative_to(REPO)}:{number}: {line.strip()}")
	return found


class TestRunnerTargets(unittest.TestCase):
	def test_the_runner_surface_is_all_present(self):
		"""A renamed file would make every other assertion here vacuous."""
		self.assertEqual(len(_present()), len(RUNNER_FILES))

	def test_no_runner_instruction_names_the_deployment_site(self):
		self.assertEqual(_hits(BENCH_ON_FRONTEND), [], "a runner is pointed at `frontend`")

	def test_the_runner_names_the_test_site(self):
		"""`assertIn` would print the whole prompt into a log a loop has to read."""
		prompt = (REPO / "scripts/prompt.md").read_text(encoding="utf-8")
		self.assertTrue(
			"bench --site bp_test_site run-tests" in prompt,
			"scripts/prompt.md names no test site for `run-tests`",
		)

	def test_the_browser_credentials_carry_no_default(self):
		self.assertEqual(_hits(CREDENTIAL_DEFAULT), [], "a browser credential still has a default")
