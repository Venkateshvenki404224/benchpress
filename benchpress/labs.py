# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The Labs list surface, assembled in a constant number of queries.

The redesigned table answers three questions the old one omitted — is this lab
deployed, where is its site, and when did it last run — so every row needs its
apps and its benches. Both are read once for the whole page, never per lab.

Bench rows go through ``frappe.get_list``, so the registered
``bench_instance_query_conditions`` scopes them: a BenchPress User is told
about their own deployment of a lab and never about anyone else's. Labs
themselves are admin-authored recipes and genuinely bounded, so the list is
returned whole rather than behind a silent page ceiling.
"""

import frappe

LAB_FIELDS = [
	"name",
	"lab_id",
	"title",
	"description",
	"frappe_version",
	"status",
	"image_tag",
	"instance_size",
	"memory_limit",
	"cpu_cores",
	"template",
	"owner",
]

BENCH_FIELDS = [
	"name",
	"lab",
	"status",
	"domain",
	"site_name",
	"started_at",
	"expires_at_ts",
]

# The fields the New lab form starts from, so their defaults are declared once —
# on the DocType — rather than again in the SPA.
FORM_DEFAULTS = (
	"frappe_version",
	"memory_limit",
	"cpu_cores",
	"iops_limit",
	"bps_limit",
	"pids_limit",
	"enable_code_server",
	"enable_ssh",
)


def get_labs() -> list[dict]:
	"""Every lab the caller may see, each with its apps and its deployment."""
	labs = frappe.get_list("Lab", fields=LAB_FIELDS, order_by="creation desc", limit_page_length=0)
	if not labs:
		return []

	lab_names = [lab.name for lab in labs]
	app_names = _app_names_by_lab(lab_names)
	benches = _benches_by_lab(lab_names)
	logos = _template_logos([lab.template for lab in labs if lab.template])
	for lab in labs:
		_attach_row_facts(lab, app_names.get(lab.name, []), benches.get(lab.name, []))
		lab.logo = logos.get(lab.template)
	return labs


def _template_logos(template_keys: list[str]) -> dict:
	"""The catalog logo each lab inherits from its template, in one query."""
	if not template_keys:
		return {}
	rows = frappe.get_all(
		"Lab Template",
		filters={"name": ("in", template_keys), "logo": ("is", "set")},
		fields=["name", "logo"],
	)
	return {row.name: row.logo for row in rows}


def _attach_row_facts(lab: dict, app_names: list[str], benches: list[dict]) -> None:
	lab.app_names = app_names
	lab.app_count = len(app_names)
	lab.bench_count = len(benches)
	lab.deployed_as = _deployed_as(benches)
	lab.last_run = _last_run(benches)


def bench_label(lab_id: str) -> str:
	"""What a bench is called on screen.

	`Bench Instance.bench_name` is `md5(user + lab)` — a stable key, but nothing
	a person can read, so every surface names a bench after its lab instead.
	Mirrored by `benchLabel` in `frontend/src/utils/labSpecs.js`; the two must
	agree, or the same bench reads as two different things on two screens.
	"""
	return f"bench-{lab_id}" if lab_id else ""


def get_lab_form_options() -> dict:
	"""What the New lab form must not hand-type: the version enum, the sizes, and the defaults.

	All three are declared server-side — the enum and the defaults on the Lab DocType, the sizes as
	`Instance Size` rows. Restating any of them in the SPA would make a new Frappe version or a
	retuned price a two-file change and let the two copies disagree.
	"""
	from benchpress.credits import config, lease

	meta = frappe.get_meta("Lab")
	versions = meta.get_field("frappe_version").options or ""
	return {
		"frappe_versions": [version for version in versions.split("\n") if version],
		"defaults": {fieldname: meta.get_field(fieldname).default for fieldname in FORM_DEFAULTS},
		"instance_sizes": lease.priced_sizes(),
		"credits_enabled": config.credits_enabled(),
	}


def _app_names_by_lab(lab_names: list[str]) -> dict:
	"""Every lab's app list, in the order the pipeline installs them.

	`Lab App` is shared with `Lab Template.apps`, and a lab built from a template keeps
	the template's name — without the `parenttype` filter every app shows up twice.
	"""
	rows = frappe.get_all(
		"Lab App",
		filters={"parent": ("in", lab_names), "parenttype": "Lab"},
		fields=["parent", "app_name"],
		order_by="idx asc",
		parent_doctype="Lab",
		limit_page_length=0,
	)
	grouped: dict[str, list[str]] = {}
	for row in rows:
		grouped.setdefault(row.parent, []).append(row.app_name)
	return grouped


def _benches_by_lab(lab_names: list[str]) -> dict:
	"""The caller's visible benches, grouped by lab, most recently touched first."""
	benches = frappe.get_list(
		"Bench Instance",
		filters={"lab": ("in", lab_names)},
		fields=BENCH_FIELDS,
		order_by="modified desc",
		limit_page_length=0,
	)
	grouped: dict[str, list[dict]] = {}
	for bench in benches:
		grouped.setdefault(bench.lab, []).append(bench)
	return grouped


def _deployed_as(benches: list[dict]) -> dict | None:
	"""Where this lab is deployed — ``None`` reads as "Never deployed"."""
	if not benches:
		return None
	bench = benches[0]
	return {
		"bench": bench.name,
		"status": bench.status,
		"site": bench.domain or bench.site_name or "",
		"expires_at_ts": bench.expires_at_ts,
	}


def _last_run(benches: list[dict]) -> str | None:
	"""The newest container start across the lab's benches."""
	starts = [bench.started_at for bench in benches if bench.started_at]
	return max(starts) if starts else None
