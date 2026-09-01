# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The root `/llms.txt`: what BenchPress is, ahead of the docs index leadtype generates."""

import re

from frappe.utils import get_url
from frappe.website.page_renderers.base_renderer import BaseRenderer
from werkzeug.wrappers import Response

from benchpress.benchpress import site_content
from benchpress.docs_assets import CACHE_CONTROL, source_root
from benchpress.public_site import public_site_enabled

ROUTE = "llms.txt"
CONTENT_TYPE = "text/plain; charset=utf-8"

# leadtype writes this section out of `docs/index.mdx`. It describes the product, which is
# what the sections above it now do, so it is dropped rather than answered twice.
GENERATED_SUMMARY_HEADING = "Overview"

SUMMARY = "Self-hosted Frappe development environments, handed out from a template in one click."

WHAT_IT_IS = (
	f"BenchPress is an open-source control plane for Frappe development environments, published "
	f"under AGPL-3.0. {site_content.HERO_SUBHEAD}\n\n"
	"It is built for teams and agencies that run Frappe apps for more than one client: one "
	"install on one server hands every developer an identical environment, instead of each "
	"laptop growing its own."
)

# Measured, with the date and the host they were measured on, from /docs/operator/prerequisites.
REQUIREMENTS = (
	"- A Linux host. `setup.sh` uses `apt` and `sysctl`; there is no macOS or Windows build.\n"
	"- An existing Frappe v16 bench. BenchPress installs into it and drives that host's Docker.\n"
	"- Docker Engine 20+ with `sysbox-runc` registered, `net.ipv4.ip_forward = 1`, and 44556/UDP "
	"open for WireGuard.\n"
	"- A domain you control, for `base_domain`.\n"
	"- Disk is the binding constraint, not CPU. Lab images measured 5.5 GB to 19.7 GB, and twelve "
	"together 54.74 GB, so provision 100 GB free for one image and 250 GB for a catalog. A 20 GB "
	"or 40 GB VPS root disk fails mid-build.\n"
	"- One CPU core per bench, the enforced floor. Measured 2026-07-02 on a two-vCPU KVM guest "
	"(AMD EPYC 9355P, 7.8 GiB RAM) on Frappe 16.25.0: migration 13.22 s, `get_labs` p95 127 ms at "
	"a 0.5-core cap."
)

PROJECT_FACTS = (
	"- License: AGPL-3.0. Self-hosting is free, needs no account and sends no telemetry.\n"
	"- The hosted build is the same repository with billing attached, so nothing is held back "
	"from the self-hosted one.\n"
	"- Award: FOSS Hack 2026 winner."
)


def build() -> str:
	blocks = [
		f"# {site_content.SITE_NAME}",
		f"> {SUMMARY}",
		section("What BenchPress is", WHAT_IT_IS),
		section("What BenchPress is not", not_lines()),
		section("Requirements", REQUIREMENTS),
		section("Install", install_block()),
		section("Pages", page_links()),
		section("Project", PROJECT_FACTS + "\n" + project_links()),
		docs_sections(),
	]
	return "\n\n".join(block for block in blocks if block) + "\n"


def section(heading: str, body: str) -> str:
	return f"## {heading}\n\n{body}"


def not_lines() -> str:
	rows = site_content.ABOUT_SEED["contrast_rows"]
	return "\n".join(f"- {row['not_text']} {row['is_text']}" for row in rows)


def install_block() -> str:
	commands = f"{site_content.INSTALL_COMMANDS}\n{site_content.SETUP_COMMAND}"
	guide = get_url(site_content.DOCS_INSTALL_ROUTE)
	return (
		"BenchPress installs into a Frappe v16 bench you already run, not as a standalone "
		"service. Two apps, then the setup script:\n\n"
		f"```bash\n{commands}\n```\n\n"
		f"Three steps remain — build the frontend, open 44556/UDP, set a base domain. {guide}"
	)


def page_links() -> str:
	landing = site_content.LANDING_SEED
	about = site_content.ABOUT_SEED
	rows = [
		("Home", "/", landing["meta_description"]),
		(
			"Self-host it",
			site_content.SELF_HOST_ROUTE,
			"What it takes to run BenchPress yourself: the six preconditions, the commands, the "
			"measured disk floor, and what breaks.",
		),
		(
			"Services",
			site_content.SERVICES_ROUTE,
			"The four engagements — managed hosting, setup on your server, custom Frappe apps "
			"and half-day training — with what each includes and what it does not.",
		),
		(
			"BenchPress and frappe_docker",
			site_content.VS_FRAPPE_DOCKER_ROUTE,
			"An honest comparison with the official Docker setup, including the rows "
			"frappe_docker wins. BenchPress is a layer above it, not a replacement.",
		),
		("About", "/about", about["meta_description"]),
		("Contact", "/contact", "Reach the people who build it, by topic."),
		("Hosted access", site_content.signup_route(), "Ask for access to the hosted build."),
		("Documentation", site_content.DOCS_ROUTE, "Three tracks: use a bench, run the host, read the API."),
		(
			"Install guide",
			site_content.DOCS_INSTALL_ROUTE,
			"Install BenchPress into a Frappe v16 bench on your own server.",
		),
	]
	return "\n".join(f"- [{label}]({get_url(route)}): {note}" for label, route, note in rows)


def project_links() -> str:
	rows = [
		("Source code", site_content.REPO_URL, "The repository the hosted build runs from."),
		("FOSS Hack 2026", site_content.AWARD_URL, "The submission and the award."),
		(
			"Community thread",
			site_content.FORUM_URL,
			"The Frappe forum thread where BenchPress was introduced, still open.",
		),
		(
			"Every documentation page as one file",
			get_url("/llms-full.txt"),
			"The full text of the documentation, for a reader that wants it in one request.",
		),
	]
	return "\n".join(f"- [{label}]({url}): {note}" for label, url, note in rows)


def docs_sections() -> str:
	path = source_root() / ROUTE
	if not path.is_file():
		return ""
	return absolutise(keep_sections(path.read_text(encoding="utf-8")))


def absolutise(body: str) -> str:
	# leadtype writes site-relative links, which a reader that fetched only this file cannot
	# resolve back to a host.
	return re.sub(r"\]\((/[^)\s]*)\)", lambda link: f"]({get_url(link.group(1))})", body)


def keep_sections(generated: str) -> str:
	# The split discards everything before the first H2, which is the generated file's own
	# title and summary.
	sections = re.split(r"^## ", generated, flags=re.MULTILINE)[1:]
	kept = [f"## {body.strip()}" for body in sections if not body.startswith(GENERATED_SUMMARY_HEADING)]
	return "\n\n".join(kept)


class LlmsTxtRenderer(BaseRenderer):
	"""Claims `/llms.txt` only where the public site is on; elsewhere the docs index still serves."""

	def can_render(self) -> bool:
		return self.path == ROUTE and public_site_enabled()

	def render(self) -> Response:
		response = Response(build())
		response.headers["Content-Type"] = CONTENT_TYPE
		response.headers["Cache-Control"] = CACHE_CONTROL
		return response
