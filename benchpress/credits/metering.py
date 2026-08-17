# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The lifecycle sites that bill: an instance starting, an instance stopping, an image built.

Only two meters exist, deliberately — running hours and custom image builds. Deploys, redeploys,
sites, devices, VPN peers and *failed* builds are all free and hard-capped instead: a rate limit
reads as fair use, a credit charge reads as nickel-and-diming. Do not add a third meter here.

`benchpress.credits.account` knows nothing about benches; this module is the translation layer.
It exists because the same transition is reachable from four places (the deploy pipeline, the
Desk buttons, the SPA action endpoint, and the reconciliation sweep), and every one of them must
be idempotent: a redeploy of a running bench, or a `restart` that never stopped anything, must
not add a second copy of the rate.

Idempotence is stored on the bench rather than inferred from its status, because status changes
for reasons that are not billing events. `credit_burn_started` set means "this instance is
currently contributing `credit_burn_rate` to its owner's burn rate", and nothing else does.
"""

import frappe
from frappe.utils import flt, now_datetime

from benchpress.credits import account, config
from benchpress.labs import bench_label

BENCH = "Bench Instance"


def on_bench_running(bench) -> None:
	"""Begin metering a bench at its lab's size rate. Idempotent."""
	if not config.credits_enabled() or bench.credit_burn_started:
		return
	lab = frappe.get_cached_doc("Lab", bench.lab)
	rate = rate_for_lab(lab)
	account.start_burn(bench.owner, bench.name, rate, label=bench_label(lab.lab_id))
	_mark_burning(bench, rate)


def on_bench_stopped(bench) -> None:
	"""Stop metering a bench, charging whatever it ran for. Idempotent.

	Also the failure path: a deploy that died settles the time its container did run and adds no
	further charge, which is what makes failed deploys free.
	"""
	if not config.credits_enabled() or not bench.credit_burn_started:
		return
	lab_id = frappe.db.get_value("Lab", bench.lab, "lab_id")
	account.stop_burn(
		bench.owner, bench.name, flt(bench.credit_burn_rate), label=bench_label(lab_id)
	)
	_mark_stopped(bench)


def on_image_built(lab) -> None:
	"""Charge the flat custom-build fee, once, for a build that succeeded.

	Reached only on a cache miss (`deploy_manager._prepare_lab_image` adopts the shared image
	otherwise) and only after the build returns, so a failed build costs nothing. The lab owner
	pays: a lab is a recipe its author owns, and everyone else deploying that recipe rides the
	shared image for free.
	"""
	if not config.credits_enabled():
		return
	account.charge(
		lab.owner,
		config.settings().custom_build_credits,
		f"Custom image build for {lab.title or lab.lab_id}",
		("Lab", lab.name),
	)


def rate_for_lab(lab) -> float:
	"""The credits-per-hour of the `Instance Size` this lab's resources resolve to."""
	size = config.size_for_lab(lab)
	return flt(size.credits_per_hour) if size else 0.0


def _mark_burning(bench, rate) -> None:
	_set_flags(bench, rate, now_datetime())


def _mark_stopped(bench) -> None:
	_set_flags(bench, 0.0, None)


def _set_flags(bench, rate, started) -> None:
	"""Write the flags without touching `modified`.

	A billing flag is not a user edit, and the deploy pipeline holds this document across several
	saves — bumping `modified` here would make the next one a timestamp mismatch.
	"""
	bench.credit_burn_rate = flt(rate)
	bench.credit_burn_started = started
	frappe.db.set_value(
		BENCH,
		bench.name,
		{"credit_burn_rate": bench.credit_burn_rate, "credit_burn_started": started},
		update_modified=False,
	)
