# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""JSON-LD for the public pages. Every claim here has to match what the page shows."""

import json

from frappe.utils import get_url

from benchpress import __version__

SITE_NAME = "BenchPress"
REPO_URL = "https://github.com/Venkateshvenki404224/benchpress"
LOGO = "/assets/benchpress/images/logo/logo-light.png"
LICENSE_URL = "https://www.gnu.org/licenses/agpl-3.0.html"

ORG_ID = "#organization"
SITE_ID = "#website"
APP_ID = "#software"


def landing(description: str, faq_items) -> str:
	graph = [organization(), website(), software(description)]
	questions = faq(faq_items)
	if questions:
		graph.append(questions)
	return encode(graph)


def about(description: str) -> str:
	return encode([organization(), page("AboutPage", "/about", "About BenchPress", description)])


def self_host(description: str) -> str:
	return encode([organization(), page("WebPage", "/self-host", "Self-host BenchPress", description)])


def contact(description: str, email: str) -> str:
	org = organization()
	# Only an address the deployment configured. The fallback constant is not guaranteed to
	# receive mail, and a dead support address is worse in structured data than none.
	if email:
		org["contactPoint"] = {
			"@type": "ContactPoint",
			"contactType": "customer support",
			"email": email,
			"url": get_url("/contact"),
		}
	return encode([org, page("ContactPage", "/contact", "Contact BenchPress", description)])


def organization() -> dict:
	return {
		"@type": "Organization",
		"@id": get_url("/") + ORG_ID,
		"name": SITE_NAME,
		"url": get_url("/"),
		"logo": get_url(LOGO),
		"sameAs": [REPO_URL],
	}


def website() -> dict:
	return {
		"@type": "WebSite",
		"@id": get_url("/") + SITE_ID,
		"name": SITE_NAME,
		"url": get_url("/"),
		"publisher": {"@id": get_url("/") + ORG_ID},
	}


def software(description: str) -> dict:
	return {
		"@type": "SoftwareApplication",
		"@id": get_url("/") + APP_ID,
		"name": SITE_NAME,
		"url": get_url("/"),
		"description": description,
		"applicationCategory": "DeveloperApplication",
		"operatingSystem": "Linux",
		"softwareVersion": __version__,
		"codeRepository": REPO_URL,
		"license": LICENSE_URL,
		"isAccessibleForFree": True,
		# The self-hosted build is the free one. No rating: nobody has reviewed it.
		"offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
		"author": {"@id": get_url("/") + ORG_ID},
	}


def faq(items) -> dict | None:
	rows = [
		{
			"@type": "Question",
			"name": row.question,
			"acceptedAnswer": {"@type": "Answer", "text": row.answer},
		}
		for row in items or []
		if row.get("question") and row.get("answer")
	]
	return {"@type": "FAQPage", "mainEntity": rows} if rows else None


def page(kind: str, route: str, name: str, description: str) -> dict:
	return {
		"@type": kind,
		"url": get_url(route),
		"name": name,
		"description": description,
		"isPartOf": {"@id": get_url("/") + SITE_ID},
	}


def encode(graph: list) -> str:
	body = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)
	# A `</script>` inside any string value would end the block early.
	return body.replace("<", "\\u003c")
