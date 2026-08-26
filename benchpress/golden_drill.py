# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Setup, measurement and teardown for `scripts/golden_drill.py`, the golden drill.

Nothing here is whitelisted, and nothing here may become whitelisted: `cleanup` deletes with
`force=True` and has no business being reachable over HTTP. The harness reaches it through
`bench --site frontend execute benchpress.golden_drill.<fn>`, and deploys through the shipped
`create_bench` endpoint.

The two arms of the drill run the **same lab**, so the image, the apps, the host and the minute
are held still and the only difference is whether the site is restored or created.
`BenchPress Settings.restore_from_golden` is what switches them, which is a site setting rather
than something the drill owns: `setup` hands its previous value back and the harness puts it
back in a `finally`.

Cleanup filters on `golden-drill@example.com`, a user this module is the only thing that mints.
Nothing else on the site ever owns a bench under it, which is what makes an owner filter safe
here where it would not be on a real account.
"""

import frappe
from frappe.utils import cint, flt
from frappe.utils.password import get_decrypted_password

from benchpress.credits import account
from benchpress.deploy_manager import GOLDEN_RESTORED
from benchpress.deploy_pipeline import parse_step_line

ACCOUNT = "Credit Account"
ADMISSION = "Bench Admission"
BENCH = "Bench Instance"
DEPLOY_LOG = "Deploy Log"
LEDGER = "Credit Ledger Entry"
SETTINGS = "BenchPress Settings"

DRILL_USER = "golden-drill@example.com"
DRILL_ROLE = "BenchPress User"

# The label every drilled site is named from, so a row this drill made says so.
SITE_PREFIX = "golddrill-"

# Funded past anything a deploy could be refused for: the drill measures how long a site takes,
# not what it costs, and a shortfall halfway through a run would measure nothing at all.
DRILL_BALANCE = 100000.0


def setup(lab: str, cold: int = 0) -> dict:
	"""Open the drill account, point it at a real lab, and set the arm this run measures."""
	lab_doc = frappe.get_doc("Lab", lab)
	if lab_doc.status != "Ready" or not lab_doc.image_tag:
		frappe.throw(f"Lab '{lab}' has no built image to drill.")

	user = _ensure_user()
	_fund(user)
	restore_before = cint(frappe.db.get_single_value(SETTINGS, "restore_from_golden"))
	_set_restore(0 if cint(cold) else restore_before)
	frappe.db.commit()  # nosemgrep -- the deploy runs in a worker that cannot see uncommitted fixtures
	return {
		"user": user,
		"api_key": frappe.db.get_value("User", user, "api_key"),
		"api_secret": _api_secret(user),
		"base_domain": frappe.db.get_single_value(SETTINGS, "base_domain"),
		"lab": lab,
		"image_tag": lab_doc.image_tag,
		"site_label": f"{SITE_PREFIX}{lab_doc.lab_id}",
		"restore_before": restore_before,
		"restoring": bool(0 if cint(cold) else restore_before),
	}


def restore(restore_before: int) -> dict:
	"""Put the site's own golden switch back."""
	_set_restore(cint(restore_before))
	frappe.db.commit()  # nosemgrep -- the switch must go back even if the harness dies mid-run
	return {"restore_from_golden": cint(restore_before)}


def measure(bench: str) -> dict:
	"""One bench's newest Deploy Log, as the numbers the drill compares.

	`site_seconds` is the gap between the `site` and `assets` markers, which is the site step's
	own duration and the only place it survives after the run.
	"""
	rows = frappe.get_all(
		DEPLOY_LOG,
		filters={"bench": bench},
		fields=["name", "message"],
		order_by="creation desc",
		limit=1,
	)
	if not rows:
		return {"deploy_log": None}
	message = rows[0].message or ""
	marks = {}
	for line in message.splitlines():
		step = parse_step_line(line)
		if step:
			marks[step["step_key"]] = step["step_elapsed"]
	return {
		"deploy_log": rows[0].name,
		"site_seconds": _gap(marks, "site", "assets"),
		"total_seconds": marks.get("complete"),
		"restored": GOLDEN_RESTORED in message,
	}


def cleanup() -> dict:
	"""Remove every bench the drill deployed, through the same teardown the delete action runs."""
	from benchpress.api import _delete_bench

	removed = []
	for name in _drill_benches():
		try:
			_delete_bench(frappe.get_doc(BENCH, name))
			removed.append(name)
		except Exception:
			# Named rather than swallowed: a drill container the harness cannot reach is an
			# operator's problem, not a silent leak.
			frappe.logger("benchpress").warning(f"golden drill: could not tear down {name}")
	frappe.db.delete(ADMISSION, {"account": DRILL_USER})
	frappe.db.delete(LEDGER, {"account": DRILL_USER})
	frappe.db.delete(ACCOUNT, {"user": DRILL_USER})
	frappe.db.commit()  # nosemgrep -- cleanup on a host serving real tenants must be durable
	return {"removed": removed, "left": _drill_benches()}


def _gap(marks: dict, start: str, end: str) -> float | None:
	if start not in marks or end not in marks:
		return None
	return round(marks[end] - marks[start], 1)


def _set_restore(value: int) -> None:
	frappe.db.set_single_value(SETTINGS, "restore_from_golden", cint(value))
	frappe.clear_document_cache(SETTINGS, SETTINGS)


def _drill_benches() -> list[str]:
	return frappe.get_all(BENCH, filters={"owner": DRILL_USER}, pluck="name")


def _ensure_user() -> str:
	if not frappe.db.exists("User", DRILL_USER):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": DRILL_USER,
				"first_name": "Golden",
				"last_name": "Drill",
				"send_welcome_email": 0,
				"roles": [{"role": DRILL_ROLE}],
			}
		).insert(ignore_permissions=True)
	user = frappe.get_doc("User", DRILL_USER)
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
