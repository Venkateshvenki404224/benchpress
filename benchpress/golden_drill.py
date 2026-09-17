# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Setup, measurement and teardown for `scripts/golden_drill.py`, reached only through `bench execute`.

Never whitelist anything here: `cleanup` deletes drill users and their benches with `force=True`.
"""

import re

import frappe
from frappe.utils import cint, flt
from frappe.utils.password import get_decrypted_password

from benchpress.credits import account
from benchpress.deploy_manager import GOLDEN_RESTORED, SITE_TIMINGS_PREFIX
from benchpress.deploy_pipeline import COMPLETE_KEY, parse_step_line

ACCOUNT = "Credit Account"
ADMISSION = "Bench Admission"
BENCH = "Bench Instance"
DEPLOY_LOG = "Deploy Log"
LEDGER = "Credit Ledger Entry"
SETTINGS = "BenchPress Settings"

DRILL_USER = "golden-drill-{n}@example.com"
DRILL_USER_LIKE = "golden-drill-%@example.com"
DRILL_USER_NAME = re.compile(r"golden-drill-\d+@example\.com")
DRILL_ROLE = "BenchPress User"
DRILL_ROW_LIMIT = 500

SITE_PREFIX = "golddrill-"

DRILL_BALANCE = 100000.0


def setup(lab: str, cold: int = 0, concurrent: int = 1) -> dict:
	"""Open one drill account per concurrent deploy, point them at a real lab, and set the arm."""
	lab_doc = frappe.get_doc("Lab", lab)
	if lab_doc.status != "Ready" or not lab_doc.image_tag:
		frappe.throw(f"Lab '{lab}' has no built image to drill.")

	users = [_drill_user(n, lab_doc.lab_id) for n in range(1, max(1, cint(concurrent)) + 1)]
	restore_before = cint(frappe.db.get_single_value(SETTINGS, "restore_from_golden"))
	_set_restore(0 if cint(cold) else restore_before)
	frappe.db.commit()  # nosemgrep -- the deploy runs in a worker that cannot see uncommitted fixtures
	return {
		"users": users,
		"base_domain": frappe.db.get_single_value(SETTINGS, "base_domain"),
		"lab": lab,
		"image_tag": lab_doc.image_tag,
		"restore_before": restore_before,
		"restoring": bool(0 if cint(cold) else restore_before),
	}


def restore(restore_before: int) -> dict:
	"""Put the site's own golden switch back."""
	_set_restore(cint(restore_before))
	frappe.db.commit()  # nosemgrep -- the switch must go back even if the harness dies mid-run
	return {"restore_from_golden": cint(restore_before)}


def measure(bench: str) -> dict | None:
	"""One bench's newest Deploy Log as the numbers the drill compares, or None for an unfinished run.

	`site_seconds` is the gap between the `site` and `assets` markers, the site step's own duration.
	"""
	rows = frappe.get_all(
		DEPLOY_LOG,
		filters={"bench": bench},
		fields=["name", "message"],
		order_by="creation desc",
		limit=1,
	)
	if not rows:
		return None
	message = rows[0].message or ""
	marks = {}
	timings = None
	for line in message.splitlines():
		step = parse_step_line(line)
		if step:
			marks[step["step_key"]] = step["step_elapsed"]
		elif line.startswith(SITE_TIMINGS_PREFIX):
			timings = line.removeprefix(SITE_TIMINGS_PREFIX).strip()
	if COMPLETE_KEY not in marks:
		return None
	return {
		"deploy_log": rows[0].name,
		"site_seconds": _gap(marks, "site", "assets"),
		"total_seconds": marks[COMPLETE_KEY],
		"restored": GOLDEN_RESTORED in message,
		"site_timings": timings,
	}


def cleanup() -> dict:
	"""Remove every drill user, the benches they deployed and the credit rows they hold."""
	from benchpress.api import _delete_bench

	users = _drill_users()
	removed = []
	for name in _drill_benches(users):
		try:
			_delete_bench(frappe.get_doc(BENCH, name))
			removed.append(name)
		except Exception:
			frappe.logger("benchpress").warning(f"golden drill: could not tear down {name}")
	left = _drill_benches(users)
	if users:
		frappe.db.delete(ADMISSION, {"account": ("in", users)})
		frappe.db.delete(LEDGER, {"account": ("in", users)})
		frappe.db.delete(ACCOUNT, {"user": ("in", users)})
	for user in set(users) - _owners(left):
		frappe.delete_doc("User", user, force=True, ignore_permissions=True, delete_permanently=True)
	frappe.db.commit()  # nosemgrep -- cleanup on a host serving real tenants must be durable
	return {"removed": removed, "left": left}


def _gap(marks: dict, start: str, end: str) -> float | None:
	if start not in marks or end not in marks:
		return None
	return round(marks[end] - marks[start], 1)


def _set_restore(value: int) -> None:
	frappe.db.set_single_value(SETTINGS, "restore_from_golden", cint(value))
	frappe.clear_document_cache(SETTINGS, SETTINGS)


def _drill_user(n: int, lab_id: str) -> dict:
	"""The `n`th drill user, funded, with its API token and the one site label it deploys under."""
	user = _ensure_user(DRILL_USER.format(n=n))
	_fund(user)
	return {
		"user": user,
		"api_key": frappe.db.get_value("User", user, "api_key"),
		"api_secret": _api_secret(user),
		"site_label": f"{SITE_PREFIX}{lab_id}-{n}",
	}


def _drill_users() -> list[str]:
	candidates = frappe.get_all(
		"User", filters={"name": ("like", DRILL_USER_LIKE)}, pluck="name", limit=DRILL_ROW_LIMIT
	)
	return [name for name in candidates if DRILL_USER_NAME.fullmatch(name)]


def _drill_benches(users: list[str]) -> list[str]:
	if not users:
		return []
	return frappe.get_all(BENCH, filters={"owner": ("in", users)}, pluck="name", limit=DRILL_ROW_LIMIT)


def _owners(benches: list[str]) -> set[str]:
	if not benches:
		return set()
	return set(frappe.get_all(BENCH, filters={"name": ("in", benches)}, pluck="owner", limit=DRILL_ROW_LIMIT))


def _ensure_user(email: str) -> str:
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Golden",
				"last_name": "Drill",
				"send_welcome_email": 0,
				"roles": [{"role": DRILL_ROLE}],
			}
		).insert(ignore_permissions=True)
	user = frappe.get_doc("User", email)
	if DRILL_ROLE not in {row.role for row in user.roles}:
		user.append("roles", {"role": DRILL_ROLE})
	user.api_key = user.api_key or frappe.generate_hash(length=15)
	if not _api_secret(user.name):
		user.api_secret = frappe.generate_hash(length=15)
	user.save(ignore_permissions=True)
	return user.name


def _api_secret(user: str) -> str | None:
	# Absent rather than an exception: the row exists before its key does.
	return get_decrypted_password("User", user, "api_secret", raise_exception=False)


def _fund(user: str) -> None:
	account.ensure_account(user)
	frappe.db.set_value(
		ACCOUNT, user, {"balance": flt(DRILL_BALANCE), "reserved_credits": 0.0}, update_modified=False
	)
