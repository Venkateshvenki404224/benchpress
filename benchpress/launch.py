# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""One click, one job: build the lab's image if it has none, then deploy a bench from it."""

# Chaining the two halves through two enqueues was the obvious shape and the wrong one — a worker
# restarting between them drops the deploy on the floor, and the user is left with a built image,
# no bench and nothing that says so. One job holds the whole run, and one `Deploy Log` records it,
# so the stepper the SPA renders reads the build and the deploy as the single thing they are.
#
# `deploy_manager._prepare_lab_image` still refuses to build inside a deploy, and that invariant
# is what this module is built around rather than against: the build happens HERE, ahead of the
# deploy, and the deploy that follows finds the image already on the host.
#
# A new module rather than a function in `deploy_manager` or `lifecycle`: it is the only place
# that needs both, and it can import both at module scope. Nothing imports `launch`, so there is
# no cycle to create.

import frappe
from frappe.utils.synchronization import filelock

from benchpress import addressing, deploy_manager, image_cache, lifecycle, notifications
from benchpress.benchpress.doctype.bench_instance.bench_instance import DEPLOY_JOB_TIMEOUT
from benchpress.deploy_pipeline import DeployPipeline

# A launch is a build and a deploy in one job, so its ceiling is both of theirs. A timeout under
# that sum would kill a legitimate run at whichever half happened to be second.
LAUNCH_JOB_TIMEOUT = image_cache.BUILD_TIMEOUT + DEPLOY_JOB_TIMEOUT


def run_launch(bench_name: str, size: str | None = None) -> None:
	"""Build what this bench needs, then deploy it. The whole of one click."""
	bench = frappe.get_doc("Bench Instance", bench_name)
	lab = frappe.get_doc("Lab", bench.lab)
	writer, deploy_log = lifecycle.open_deploy_log(bench_name)
	if not _built(lab, bench, writer, deploy_log):
		return
	lifecycle.deploy_bench(bench_name, size, deploy_log)
	_announce(bench_name)


def _built(lab, bench, writer, deploy_log) -> bool:
	"""Produce the image this deploy needs. False when the launch stopped here."""
	if image_cache.is_ready(lab):
		return True
	try:
		# Step 2 of eleven, opened before Docker is touched, so the stepper reads
		# "Preparing the lab image — running" for the whole build with Docker's own
		# output streaming underneath it on `lab_build_log`.
		DeployPipeline(writer).step("image")
		# A wait, not a skip: two launches of the same unbuilt lab must not both run `docker
		# build` against one tag and both charge `metering.on_image_built`. The loser waits.
		with filelock(f"lab_build_{lab.name}", timeout=image_cache.BUILD_TIMEOUT):
			# A launch that queued behind another one may find the image already
			# built; the memoised tag set is from before that build.
			image_cache.clear_cached_tags()
			lab.reload()
			if not image_cache.is_ready(lab):
				# `bench.owner`, never `lab.owner`: the build stream and the Build
				# Log row belong to whoever is watching, and a shared lab's author
				# is usually someone else.
				deploy_manager._run_build(lab, bench.owner)
		lab.reload()
	except Exception as e:
		deploy_manager.record_build_failure(lab.name, bench.owner)
		bench.reload()
		# Releases the admission slot and the credit hold, and sets Error.
		lifecycle.errored(bench, None, writer)
		writer(f"=== Deploy failed: the lab image could not be built: {e!s} ===", "error")
		frappe.db.set_value("Deploy Log", deploy_log, "log_type", "error")
		frappe.db.commit()  # nosemgrep -- the run's outcome must survive its failure
		return False
	return True


def _announce(bench_name: str) -> None:
	"""The notice that outlives a closed browser, because a build can run 40 minutes."""
	# `_deploy_bench` swallows its own exception, so the outcome is read back from
	# the row rather than inferred from a return. The desk alert already fired
	# inside `_deploy_bench`; this is the channel that survives the session.
	bench = frappe.get_doc("Bench Instance", bench_name)
	title = frappe.db.get_value("Lab", bench.lab, "title") or bench.lab
	if bench.status == "Running":
		url = bench.public_url or addressing.tunnel_site_url(bench.as_dict()) or ""
		notifications.email_owner(
			bench.owner, f"{title} is ready", f"Your {title} lab is deployed and running. {url}".strip()
		)
		return
	notifications.email_owner(
		bench.owner,
		f"{title} could not be deployed",
		f"The launch of {title} stopped before the bench was running. Open the lab to see why.",
	)
