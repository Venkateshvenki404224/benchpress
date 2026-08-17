# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""What the enforcement sweep and the reaper say, and where they say it.

The copy lives here rather than inline so the sweep reads as decisions and this reads as sentences.
Every notice names the number that triggered it and what to do about it — a warning a user cannot
act on is just noise, and noise gets muted.

Channel is chosen by how long the notice has to survive. A stop or a TTL warning is about
something happening now, so it is a desk alert. A reap warning is about a deletion two days out:
nobody is watching a sidebar then, so that one is an email.
"""

import frappe
from frappe import _
from frappe.utils import flt, get_datetime, now_datetime

from benchpress import notifications
from benchpress.labs import bench_label

BENCH = "Bench Instance"


def warn_ttl(bench, minutes_left: int) -> None:
	notifications.notify_owner(
		bench.owner,
		_("{0} auto-stops in about {1} minutes. Buy an Always On Pass to keep it up.").format(
			_label(bench), minutes_left
		),
		BENCH,
		bench.name,
	)


def warn_low_balance(user: str, available, threshold) -> None:
	notifications.notify_owner(
		user,
		_(
			"Credits running low: {0} left, below your {1} warning level. Top up before your instances stop."
		).format(flt(available, 2), flt(threshold, 2)),
		"Credit Account",
		user,
	)


def announce_stop(bench, reason: str) -> None:
	notifications.notify_owner(
		bench.owner,
		_("{0} was stopped: {1}. Start it again whenever you need it.").format(_label(bench), reason),
		BENCH,
		bench.name,
	)


def warn_reap(bench, days_left: int) -> None:
	notifications.email_owner(
		bench.owner,
		_("{0} will be deleted in {1} days").format(_label(bench), days_left),
		_(
			"<p>{0} has been stopped long enough that BenchPress will delete its container and data in {1} days.</p><p>Start it once to keep it. The lab it was built from is kept either way, so a deleted instance is one click from running again — but anything inside the instance is not.</p>"
		).format(_label(bench), days_left),
	)


def announce_reap(bench) -> None:
	notifications.notify_owner(
		bench.owner,
		_("{0} was deleted after sitting stopped. Its lab is intact — deploy it again to rebuild.").format(
			_label(bench)
		),
		BENCH,
		bench.name,
	)


# --- Saying it at most once ---------------------------------------------------


def already_warned(stamp, since) -> bool:
	"""Whether a warning stamp still describes the current run or stopped period.

	"At most once per session" is a property of the notice, so it is decided here rather than in
	each caller: a stamp older than the moment the period began has been superseded by it.
	"""
	if not stamp:
		return False
	if not since:
		return True
	return get_datetime(stamp) >= get_datetime(since)


def stamp_warning(bench_name: str, field: str) -> None:
	"""Record that a warning went out, without touching `modified`.

	The reaper reads `modified` as stopped-since, so a write that bumped it would postpone the
	deletion every time it warned about it.
	"""
	frappe.db.set_value(BENCH, bench_name, field, now_datetime(), update_modified=False)


def _label(bench) -> str:
	"""What the instance is called on screen. `bench.name` is an md5, which explains nothing.

	The sweep already carries `lab_id` on its rows, so this costs it nothing; the reaper hands over
	a document and pays one indexed read for the same sentence.
	"""
	lab_id = bench.get("lab_id") or frappe.db.get_value("Lab", bench.get("lab"), "lab_id")
	return bench_label(lab_id) or bench.name
