# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The eleven steps of a deploy, and how a run reports them.

A deploy takes minutes and used to report itself as one scrolling wall of text.
Every boundary in the pipeline now emits a `step` line that names the step, its
position and how far into the run it started, so the SPA can render a stepper
whose state is a reading of the log rather than a client-side timer.

Two rules hold this together:

* **The `=== … ===` wrapper is load-bearing.** `LogViewer.vue` and
  `lab_detail._parse_failure` both parse it, and every log written before this
  module existed only has that. Step metadata goes *inside* the marker, never in
  place of it, so historical runs keep rendering.
* **The step order is the order the code runs**, which is not the order
  `DESIGN_BRIEF` §4 lists. See `DEPLOY_STEPS`.
"""

import re
import time
from dataclasses import dataclass

import frappe


@dataclass(frozen=True)
class DeployStep:
	"""One boundary in the deploy pipeline."""

	key: str
	label: str


# The order below is `deploy_manager._deploy_bench`'s own order. DESIGN_BRIEF §4
# lists the WireGuard peer at position 10; `_setup_container_vpn` actually runs
# it at 5, right after the container reports an IP. The stepper is a report of
# the run, not of the plan, so the code wins — do not "correct" this to the
# brief's order.
DEPLOY_STEPS = (
	DeployStep("infrastructure", "Checking shared infrastructure"),
	DeployStep("image", "Preparing the lab image"),
	DeployStep("container", "Creating the container"),
	DeployStep("container_ip", "Waiting for the container IP"),
	DeployStep("vpn_peer", "Configuring the WireGuard peer"),
	DeployStep("site_config", "Writing common_site_config.json"),
	DeployStep("site", "Creating the site"),
	DeployStep("assets", "Building assets"),
	DeployStep("ssh_user", "Provisioning the SSH user"),
	DeployStep("code_server", "Provisioning code-server"),
	DeployStep("complete", "Deploy complete"),
)

STEP_TOTAL = len(DEPLOY_STEPS)
STEP_INDEX = {step.key: index for index, step in enumerate(DEPLOY_STEPS, start=1)}

# `=== Step 4/11: Waiting for the container IP [container_ip @14.2s] ===`
STEP_LINE = re.compile(
	r"^===\s*Step\s+(?P<index>\d+)/(?P<total>\d+):\s*(?P<label>.*?)\s*"
	r"\[(?P<key>[a-z_]+)\s*@(?P<elapsed>\d+(?:\.\d+)?)s\]\s*===$"
)


def format_step_line(key: str, elapsed_seconds: float) -> str:
	"""The human sentence first, the machine fields second, both in one line."""
	index = STEP_INDEX[key]
	step = DEPLOY_STEPS[index - 1]
	return f"=== Step {index}/{STEP_TOTAL}: {step.label} [{step.key} @{elapsed_seconds:.1f}s] ==="


def parse_step_line(line: str) -> dict | None:
	"""The step a line opens, or ``None`` when it opens no step."""
	match = STEP_LINE.match(line.strip())
	if not match:
		return None
	return {
		"step_key": match["key"],
		"step_index": int(match["index"]),
		"step_total": int(match["total"]),
		"step_label": match["label"],
		"step_elapsed": float(match["elapsed"]),
	}


class DeployLogWriter:
	"""One log line: published to the run's owner, then appended to the document.

	The publish is scoped to the owning user's room. It used to be a site-wide
	broadcast that `LabDetail.vue` filtered client-side — by the time the filter
	ran, every connected browser already held every other tenant's deploy log.

	`after_commit=False` is deliberate and unchanged: the SPA appends per line,
	so a line held back until the transaction commits arrives too late to be a
	live log.
	"""

	def __init__(self, doctype: str, log_name: str, event: str, context: dict, user: str):
		self.doctype = doctype
		self.log_name = log_name
		self.event = event
		self.context = context
		self.user = user

	def __call__(self, line: str, log_type: str = "info", step: dict | None = None) -> None:
		self._publish(line, log_type, step)
		self._append(line)

	def _publish(self, line: str, log_type: str, step: dict | None) -> None:
		# The four original keys are what the SPA appends on; step metadata is
		# purely additive, so an older client keeps working.
		message = {**self.context, "log": line, "type": log_type}
		if step:
			message.update(step)
		frappe.publish_realtime(
			event=self.event,
			message=message,
			user=self.user,
			after_commit=False,
		)

	def _append(self, line: str) -> None:
		current = frappe.db.get_value(self.doctype, self.log_name, "message") or ""
		frappe.db.set_value(
			self.doctype, self.log_name, "message", current + line + "\n", update_modified=False
		)
		frappe.db.commit()


class DeployPipeline:
	"""Emits the step markers of one run, with elapsed times measured, not guessed.

	Elapsed is the offset from the start of the run, written into every marker,
	so a step's duration is the gap to the next marker — recoverable from the
	stored log long after the run ended, not only while it streams.
	"""

	def __init__(self, write: DeployLogWriter):
		self.write = write
		self._started_at = time.monotonic()

	@property
	def elapsed(self) -> float:
		return time.monotonic() - self._started_at

	def step(self, key: str, log_type: str = "step") -> None:
		"""Open a step. The terminal step passes its own type so the log stays typed."""
		elapsed = self.elapsed
		self.write(format_step_line(key, elapsed), log_type, self._payload(key, elapsed))

	def log(self, line: str, log_type: str = "info") -> None:
		"""A plain line inside the step that is currently open."""
		self.write(line, log_type)

	def _payload(self, key: str, elapsed: float) -> dict:
		index = STEP_INDEX[key]
		return {
			"step_key": key,
			"step_index": index,
			"step_total": STEP_TOTAL,
			"step_label": DEPLOY_STEPS[index - 1].label,
			"step_elapsed": round(elapsed, 1),
		}
