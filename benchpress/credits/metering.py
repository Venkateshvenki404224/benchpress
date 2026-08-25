# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The lifecycle sites that bill: an instance starting, an instance stopping, an image built.

There is one lease and one meter. A deploy buys a fixed window at the moment its container
reaches `Running`, charged once through `account.charge`; the only thing still metered is a
custom image build. Sites, devices, VPN peers, redeploys and *failed* builds are free and
hard-capped instead — a rate limit reads as fair use, a credit charge reads as nickel-and-diming.
Do not add a second meter here.

`benchpress.credits.account` knows nothing about benches and `benchpress.credits.lease` knows
nothing about money; this module is the translation layer between them. It exists because the
same transition is reachable from four places (the deploy pipeline, the Desk buttons, the SPA
action endpoint, and the reconciliation sweep), and every one of them must be idempotent: a
redeploy of a running bench, or a `restart` that never stopped anything, must not buy a second
window.

Idempotence is `lease_state`, not status, because status changes for reasons that are not
billing events. `Active` means "this instance is inside a window somebody paid for".
"""

import frappe
from frappe.utils import flt

from benchpress.credits import account, config, lease, passes
from benchpress.labs import bench_label


def on_bench_running(bench) -> None:
	"""Charge the lease and start its clock. Idempotent.

	Called from every transition into `Running`, before the caller saves `status`, so the charge
	and the deadline land in the same transaction as the status they belong to. Nothing charges
	at deploy: a cold image build takes minutes, and a window that opens before the container
	exists sells time the build ate.

	An instance holding an unexpired `Always On Pass` is prepaid, so it buys no window and gets
	no deadline — charging for a lease on top of a monthly price would sell the same time twice.
	"""
	if not config.credits_enabled() or bench.get("lease_state") == lease.ACTIVE:
		return
	if passes.has_active_pass(bench.name):
		return
	lab = frappe.get_cached_doc("Lab", bench.lab)
	plan = lease.plan_for(lab)
	if not plan:
		return
	charge_lease(bench, lab, plan)
	lease.arm(bench, lab, plan)


def charge_lease(bench, lab, plan, request_id: str | None = None) -> float:
	"""Debit one lease window and return what it cost.

	`request_id` makes the debit idempotent for a caller that may deliver the same click more
	than once — a renew from three tabs. A deploy needs none: `lease_state` is its guard.
	"""
	cost = lease.cost_of(lab, plan)
	label = bench_label(lab.lab_id) or bench.name
	account.charge(
		bench.owner,
		cost,
		f"{label} — {plan.plan_label} lease",
		("Bench Instance", bench.name),
		request_id=request_id,
	)
	return cost


def on_bench_stopped(bench) -> None:
	"""Clear the lease clock. Idempotent, and free on a bench that never held one.

	A stopped row must not keep a deadline that has passed: the next start would set `Running`
	beside it and the following sweep would claim the bench straight back.

	This is also the failure path, and it charges nothing — a deploy that died before `Running`
	never bought a window, which is what makes failed deploys free.
	"""
	lease.disarm(bench)


def on_pass_purchased(bench) -> None:
	"""Release an instance from its lease clock now that it is prepaid. Idempotent.

	Only the clock stops — the container keeps running, which is the whole point of the pass. The
	window already bought is not refunded, so the buyer pays per lease up to the purchase and by
	the month after it, and never for both at once.
	"""
	lease.disarm(bench)


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
