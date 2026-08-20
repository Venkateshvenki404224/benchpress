# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""One image per lab, tagged by the lab's own identity.

A Lab's image is tagged `benchpress/<lab_id>:lab` — static, not derived from the build spec. The
first Lab created from a catalog template gets that template's own key as its `lab_id`
(`lab_templates.available_lab_id`), so a template's prewarmed image and the first unmodified Lab
built from it naturally resolve to the same tag with no extra bookkeeping. A Lab that diverges
from its template (edited apps/version) needs its own rebuild — see `Lab.validate()`'s staleness
check, which resets `status` to `Draft` when `build_spec` no longer matches what was last built.

Docker is asked for its image list **once** per request or job: `cached_tags` memoises the set on
`frappe.local`, so resolving a queue of labs costs one round trip, not one per lab.
"""

import frappe
from frappe.utils import cstr

from benchpress import lab_templates
from benchpress.request_cache import clear_local_cache, local_cache

CACHE_REPOSITORY = "benchpress"
TAGS_ATTRIBUTE = "benchpress_cached_image_tags"

BUILD_TIMEOUT = 10800
SWEEP_TIMEOUT = 600
PREWARM_JOB_ID = "benchpress_prewarm_catalog"
SWEEP_JOB_ID = "benchpress_sweep_cached_images"


def build_spec(lab_doc) -> dict:
	"""Everything that decides the image contents, normalised so equal recipes compare equal.

	`app_name` is lowercased because the build lowercases it too — `ERPNext` and `erpnext`
	produce the same image, so they must produce the same hash.
	"""
	return {
		"frappe_version": cstr(lab_doc.frappe_version).strip(),
		"apps": sorted(
			(cstr(row.app_name).strip().lower(), cstr(row.git_url).strip(), cstr(row.branch).strip())
			for row in (lab_doc.apps or [])
		),
	}


def cache_tag(lab_doc) -> str:
	"""The static image tag this lab builds into."""
	return f"{CACHE_REPOSITORY}/{lab_doc.lab_id}:lab"


def resolve(lab_doc) -> tuple[str, bool]:
	"""`(tag, hit)` — this spec's tag, and whether that image already exists on the host."""
	tag = cache_tag(lab_doc)
	return tag, tag in cached_tags()


def cached_tags() -> set[str]:
	"""Every cached image tag on this host. One Docker round trip per request, then O(1) lookups."""
	return local_cache(TAGS_ATTRIBUTE, list_cached_tags)


def clear_cached_tags() -> None:
	"""Forget the memoised set — a build or a removal in this run has changed it."""
	clear_local_cache(TAGS_ATTRIBUTE)


def list_cached_tags() -> set[str]:
	"""Every `benchpress/<lab_id>:lab` image on this host.

	Each lab is its own repository now, not a shared one — `benchpress/*` is a glob against the
	repository name, not a fixed exact match, so it still costs one Docker round trip for every
	lab's image, not one per lab. The whole `benchpress/` namespace is no longer exclusively
	ours the way `benchpress/cache/` was, so the `:lab` tag suffix is what actually identifies an
	image this module built — the prefix alone would also catch something like a stray hand-tagged
	`benchpress/crm-lab:latest`.
	"""
	from benchpress.docker_manager import get_client

	prefix = f"{CACHE_REPOSITORY}/"
	images = get_client().images.list(name=f"{CACHE_REPOSITORY}/*")
	return {
		tag
		for image in images
		for tag in (image.tags or [])
		if tag.startswith(prefix) and tag.endswith(":lab")
	}


def template_spec(template: dict):
	"""A catalog template seen as a Lab: the fields the hash and the build read, nothing more."""
	return frappe._dict(
		lab_id=template["key"],
		title=template["title"],
		frappe_version=template["frappe_version"],
		apps=[frappe._dict(app) for app in template["apps"]],
	)


def catalog_tags() -> set[str]:
	"""The pre-warmed set. A template's image is kept even while no Lab points at it."""
	return {cache_tag(template_spec(template)) for template in lab_templates.get_templates()}


def prewarm_catalog() -> dict:
	"""Queue a build for every catalog template that has no cached image yet.

	Runs on `queue-long`, the only worker with a Docker socket, and queues **one job per
	template** so a single failing template cannot cancel the other six.
	"""
	cached = cached_tags()
	templates = lab_templates.get_templates()
	missing = [t for t in templates if cache_tag(template_spec(t)) not in cached]
	for template in missing:
		_enqueue_template_build(template)
	return {"queued": [t["key"] for t in missing], "cached": len(templates) - len(missing)}


def build_template_image(template_key: str) -> str:
	"""Build one catalog template under its content hash, with no Lab document involved."""
	from benchpress.docker_manager import build_lab_image

	tag = build_lab_image(template_spec(lab_templates.get_template(template_key)))
	frappe.logger("benchpress").info(f"Pre-warmed {tag} for template {template_key}")
	return tag


def sweep_cached_images() -> dict:
	"""Remove cached images nothing points at any more.

	A cached image outlives the Lab that built it, so without this sweep the cache is an
	unbounded disk leak — the same trap as unreaped instance volumes. Only `benchpress/cache:*`
	is ever touched; the pre-cache `benchpress/<lab_id>:latest` images are left alone.
	"""
	tags = cached_tags()
	removed = _remove_images(sorted(tags - referenced_tags()))
	clear_cached_tags()
	return {"removed": removed, "kept": len(tags) - len(removed)}


def referenced_tags() -> set[str]:
	"""Cache tags something still needs: a Lab, a bench's container, the catalog, or a live build.

	Two plucks and a set difference — O(n + m), never a query per image.
	"""
	labs = set(frappe.get_all("Lab", pluck="image_tag"))
	containers = set(frappe.get_all("Bench Instance", pluck="container_image"))
	return (labs | containers | catalog_tags() | in_flight_tags()) - {None, ""}


def in_flight_tags() -> set[str]:
	"""What the builds running right now will produce.

	A Building lab has no `image_tag` yet, so its fresh image would read as an orphan and a sweep
	could delete it out from under the deploy that is waiting for it. Hashing those labs' specs
	protects exactly those tags — a single lab stuck in Building cannot disable the whole sweep,
	which is what a blanket "defer while any build runs" guard would do. The loop is bounded by
	the number of concurrent builds, not by the number of labs.
	"""
	building = frappe.get_all("Lab", filters={"status": "Building"}, pluck="name")
	return {cache_tag(frappe.get_cached_doc("Lab", name)) for name in building}


def enqueue_prewarm_catalog() -> dict:
	"""Weekly cron and admin action alike: pre-warm on the worker that can reach Docker."""
	return _enqueue_on_long("benchpress.image_cache.prewarm_catalog", PREWARM_JOB_ID, BUILD_TIMEOUT)


def enqueue_sweep() -> dict:
	"""Weekly cron: garbage-collect on the worker that can reach Docker."""
	return _enqueue_on_long("benchpress.image_cache.sweep_cached_images", SWEEP_JOB_ID, SWEEP_TIMEOUT)


def _enqueue_on_long(method: str, job_id: str, timeout: int) -> dict:
	"""Scheduled jobs land on `queue-short`, which has no Docker socket mounted — hand them over."""
	frappe.enqueue(method, queue="long", timeout=timeout, job_id=job_id, deduplicate=True)
	return {"status": "Queued", "job_id": job_id}


def _enqueue_template_build(template: dict) -> None:
	frappe.enqueue(
		"benchpress.image_cache.build_template_image",
		template_key=template["key"],
		queue="long",
		timeout=BUILD_TIMEOUT,
		job_id=f"prewarm_image:{template['key']}",
		deduplicate=True,
	)


def _remove_images(tags: list[str]) -> list[str]:
	from benchpress.docker_manager import get_client

	client = get_client()
	removed = []
	for tag in tags:
		try:
			client.images.remove(tag)
			removed.append(tag)
		except Exception:
			frappe.log_error(title=f"Cached image not removed: {tag}", message=frappe.get_traceback())
	return removed
