# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The GitHub traffic snapshot. GitHub keeps fourteen days; these rows keep the rest."""

import requests

import frappe
from frappe.utils import cstr

DOCTYPE = "GitHub Traffic Snapshot"
REPO_KEY = "benchpress_github_repo"
TOKEN_KEY = "benchpress_github_token"

API_ROOT = "https://api.github.com"
TIMEOUT = 30


def snapshot_traffic() -> list[str]:
	"""Scheduled daily. Writes nothing at all unless a deployment configured a repo and a token."""
	repository = cstr(frappe.conf.get(REPO_KEY)).strip()
	token = cstr(frappe.conf.get(TOKEN_KEY)).strip()
	if not repository or not token:
		return []

	return GitHubTraffic(repository, token).write_snapshots()


class GitHubTraffic:
	def __init__(self, repository: str, token: str):
		self.repository = repository
		self.token = token

	def write_snapshots(self) -> list[str]:
		clones = self.by_day("/traffic/clones", "clones")
		views = self.by_day("/traffic/views", "views")
		repository = self.get("")
		referrer = top_referrer(self.get("/traffic/popular/referrers"))

		days = sorted(set(clones) | set(views))
		# The traffic window usually ends yesterday, so the point-in-time counts go on its last day.
		newest = days[-1] if days else None
		return [
			self.upsert(day, clones.get(day, {}), views.get(day, {}), repository, referrer, day == newest)
			for day in days
		]

	def upsert(
		self, day: str, clones: dict, views: dict, repository: dict, referrer: str, newest: bool
	) -> str:
		doc = self.row_for(day)
		doc.update(
			{
				"repository": self.repository,
				"snapshot_date": day,
				"clone_uniques": clones.get("uniques") or 0,
				"clone_count": clones.get("count") or 0,
				"view_uniques": views.get("uniques") or 0,
				"view_count": views.get("count") or 0,
			}
		)
		# Stars, forks and the referrer are read at this instant, so only the newest row carries them.
		if newest:
			doc.stars = repository.get("stargazers_count") or 0
			doc.forks = repository.get("forks_count") or 0
			doc.top_referrer = referrer

		doc.save(ignore_permissions=True)
		return doc.name

	def row_for(self, day: str):
		name = existing_row(self.repository, day)
		return frappe.get_doc(DOCTYPE, name) if name else frappe.new_doc(DOCTYPE)

	def by_day(self, path: str, key: str) -> dict:
		rows = self.get(path).get(key) or []
		return {cstr(row.get("timestamp"))[:10]: row for row in rows if row.get("timestamp")}

	def get(self, path: str) -> dict:
		response = requests.get(
			f"{API_ROOT}/repos/{self.repository}{path}",
			headers={
				"Accept": "application/vnd.github+json",
				"Authorization": f"Bearer {self.token}",
				"X-GitHub-Api-Version": "2022-11-28",
			},
			timeout=TIMEOUT,
		)
		response.raise_for_status()
		return response.json()


def existing_row(repository: str, day: str) -> str | None:
	table = frappe.qb.DocType(DOCTYPE)
	rows = (
		frappe.qb.from_(table)
		.select(table.name)
		.where(table.repository == repository)
		.where(table.snapshot_date == day)
		.limit(1)
	).run()
	return rows[0][0] if rows else None


def top_referrer(payload) -> str:
	if not payload:
		return ""
	return cstr(payload[0].get("referrer"))
