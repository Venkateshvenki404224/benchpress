# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import getpass
import os
import shutil
import subprocess
import sys

import frappe

from benchpress import doctor

OK = "ok"
APPLY = "apply"
FAIL = "fail"
SKIP = "skip"

SUDOERS_FILE = "/etc/sudoers.d/benchpress"
SYSCTL_CONF = "/etc/sysctl.d/99-benchpress.conf"

_TAG = {OK: "[OK]", APPLY: "[APPLY]", FAIL: "[FAIL]", SKIP: "[SKIP]"}
_ANSI = {OK: "\033[32m", APPLY: "\033[33m", FAIL: "\033[31m", SKIP: "\033[90m"}
_ANSI_RESET = "\033[0m"


def _record(status: str, step: str, detail: str, change=None, error: str | None = None) -> dict:
	return {"status": status, "step": step, "detail": detail, "change": change, "error": error}


def _passes(check_fn) -> bool:
	return all(r["status"] == doctor.PASS for r in check_fn())


class Step:
	def __init__(
		self,
		key,
		name,
		check,
		describe,
		apply,
		rollback=None,
		host_only=True,
		destructive=False,
	):
		self.key = key
		self.name = name
		self.check = check
		self.describe = describe
		self.apply = apply
		self.rollback = rollback
		self.host_only = host_only
		self.destructive = destructive


def _step_sudoers_apply() -> None:
	user = getpass.getuser()
	wg_bin = shutil.which("wg") or "/usr/bin/wg"
	wg_quick_bin = shutil.which("wg-quick") or "/usr/bin/wg-quick"
	line = f"{user} ALL=(ALL) NOPASSWD: {wg_bin}, {wg_quick_bin}\n"
	subprocess.run(["sudo", "tee", SUDOERS_FILE], input=line, capture_output=True, text=True, check=True)
	subprocess.run(["sudo", "chmod", "0440", SUDOERS_FILE], capture_output=True, text=True, check=True)


def _step_sudoers_rollback() -> None:
	subprocess.run(["sudo", "rm", "-f", SUDOERS_FILE], capture_output=True, text=True, check=False)


def _step_ip_forward_apply() -> None:
	subprocess.run(
		["sudo", "sysctl", "-w", "net.ipv4.ip_forward=1"], capture_output=True, text=True, check=True
	)
	subprocess.run(
		["sudo", "tee", SYSCTL_CONF],
		input="net.ipv4.ip_forward = 1\n",
		capture_output=True,
		text=True,
		check=True,
	)


def _step_ip_forward_rollback() -> None:
	subprocess.run(["sudo", "rm", "-f", SYSCTL_CONF], capture_output=True, text=True, check=False)


STEPS = [
	Step(
		key="sudoers",
		name="Sudoers (passwordless wg)",
		check=lambda: _passes(doctor._check_sudoers),
		describe=lambda: ["write /etc/sudoers.d/benchpress (NOPASSWD wg, wg-quick); chmod 0440"],
		apply=_step_sudoers_apply,
		rollback=_step_sudoers_rollback,
	),
	Step(
		key="ip_forward",
		name="IP forwarding",
		check=lambda: _passes(doctor._check_ip_forward) and os.path.exists(SYSCTL_CONF),
		describe=lambda: ["sysctl -w net.ipv4.ip_forward=1", f"write {SYSCTL_CONF}"],
		apply=_step_ip_forward_apply,
		rollback=_step_ip_forward_rollback,
	),
]


def _plan_summary(records: list[dict]) -> dict:
	return {
		"apply": sum(1 for r in records if r["status"] == APPLY),
		"ok": sum(1 for r in records if r["status"] == OK),
		"skip": sum(1 for r in records if r["status"] == SKIP),
	}


def _format_plan(records: list[dict], env: dict, tty: bool = False) -> str:
	lines = ["BenchPress setup plan"]
	site = env.get("site") or "?"
	bench = env.get("bench") or "?"
	location = "container" if env.get("in_container") else "host"
	lines.append(f"site: {site}  bench: {bench}  running on: {location}")
	lines.append("")

	for r in records:
		tag = _TAG.get(r["status"], "[????]")
		if tty:
			tag = f"{_ANSI.get(r['status'], '')}{tag}{_ANSI_RESET}"
		lines.append(f"{tag} {r['step']}: {r['detail']}")
		for change in r.get("change") or []:
			lines.append(f"        {change}")

	counts = _plan_summary(records)
	lines.append("")
	lines.append(f"Plan: {counts['apply']} to apply, {counts['ok']} already done, {counts['skip']} skipped")
	return "\n".join(lines)


def _filter_steps(only) -> list[Step]:
	keys = None if only is None else ({only} if isinstance(only, str) else set(only))
	return [s for s in STEPS if keys is None or s.key in keys]


def plan(only=None) -> list[dict]:
	records = []
	for step in _filter_steps(only):
		if step.host_only and doctor._in_docker():
			records.append(_record(SKIP, step.name, "run on the host"))
		elif step.check():
			records.append(_record(OK, step.name, "already applied"))
		else:
			records.append(_record(APPLY, step.name, "would apply", change=step.describe()))
	return records


def run(
	dry_run: bool = False,
	assume_yes: bool = False,
	as_json: bool = False,
	only=None,
	strict: bool = False,
):
	"""Print the BenchPress host-setup plan; apply pending steps unless dry-run."""
	records = plan(only=only)
	env = {
		"site": getattr(frappe.local, "site", None),
		"bench": doctor._bench_dir(),
		"in_container": doctor._in_docker(),
	}

	if as_json:
		print(frappe.as_json(records))
	else:
		print(_format_plan(records, env, tty=sys.stdout.isatty()))

	if dry_run:
		return None

	failed = False
	for step in _filter_steps(only):
		if step.host_only and doctor._in_docker():
			continue
		if step.check():
			continue
		try:
			step.apply()
			print(f"[OK] {step.name}: applied")
		except Exception as e:
			frappe.log_error(title=f"setup step failed: {step.key}", message=frappe.get_traceback())
			print(f"[FAIL] {step.name}: apply failed: {e}")
			failed = True
			break

	if strict and failed:
		raise SystemExit(1)
	return None
