#!/usr/bin/env python3
"""Push `docs/*.mdx` into the Wiki Pages that serve benchpress.cloud/docs.

The repo is the source of truth; the wiki is a render target that has drifted from it.
"""

# Why this exists: the documentation has had two sources of truth. `docs/*.mdx` is gated in CI
# (lint at zero warnings, a score floor, and a drift check on the generated output), while the
# published site is the `wiki` app, whose pages live in the database rather than in git.
# Nothing connected them, so fixes merged here never reached a reader at benchpress.cloud/docs.
# This script is the connection. `llms.txt` needs none of it: the app serves that straight
# from the committed `docs-site/` tree (benchpress/docs_assets.py).
#
# Three mappings, all verified against the live site rather than assumed:
#   route    `docs/operator/install.mdx`      -> `docs/operator/install`
#            `docs/operator/index.mdx`        -> `docs/operator`
#   images   `](../images/user/x/01.png)`     -> `](/files/docs-images/user/x/01.png)`
#   links    already site-absolute (`/docs/...`) and need no rewrite.
#
# It never deletes. A page on the site with no `.mdx` behind it is reported and left alone,
# because this repo is not the only thing that may have put it there.

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
DEFAULT_URL = "https://benchpress.cloud"
IMAGE_PREFIX = "/files/docs-images/"
TIMEOUT = 30

# The public name is behind Cloudflare, which answers a machine client with error 1010 rather
# than with the endpoint. `--url` takes the origin directly when that happens.
CLOUDFLARE_BLOCK = "1010"
# Cloudflare 403s the default `Python-urllib/3.x` agent outright, before the site is reached.
# Every request carries a real one, or nothing here works against the public name.
USER_AGENT = "Mozilla/5.0 (compatible; benchpress-publish-docs)"


class PublishError(RuntimeError):
	pass


def parse_front_matter(text: str) -> tuple[dict, str]:
	"""Split leading `---` YAML from the body. Only flat `key: value` pairs are used."""
	if not text.startswith("---"):
		return {}, text
	end = text.find("\n---", 3)
	if end == -1:
		return {}, text
	raw, body = text[3:end], text[end + 4 :]
	meta = {}
	for line in raw.splitlines():
		key, sep, value = line.partition(":")
		if sep and not key.startswith((" ", "\t", "#")):
			meta[key.strip()] = value.strip().strip("\"'")
	return meta, body.lstrip("\n")


def route_for(path: Path) -> str:
	"""The wiki route an `.mdx` file publishes to."""
	rel = path.relative_to(DOCS_DIR).with_suffix("")
	parts = list(rel.parts)
	if parts[-1] == "index":
		parts.pop()
	return "/".join(["docs", *parts])


def rewrite_images(body: str) -> tuple[str, set[str]]:
	"""Point relative image paths at the site's file store, and report what they resolve to."""
	seen: set[str] = set()

	def replace(match: re.Match) -> str:
		target = IMAGE_PREFIX + match.group("path")
		seen.add(target)
		return f"]({target})"

	# `../images/x.png` from a nested page and `./images/x.png` from the root index both land in
	# the same store; the leading dots are what differ, never the tail.
	pattern = re.compile(r"\]\((?:\.\./|\./)+images/(?P<path>[^)]+)\)")
	return pattern.sub(replace, body), seen


def page_payload(path: Path) -> dict:
	meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
	content, images = rewrite_images(body)
	title = meta.get("title")
	if not title:
		raise PublishError(f"{path}: no `title` in front matter, so the wiki page would be unnamed")
	return {
		"route": route_for(path),
		"title": title,
		"meta_description": meta.get("description", ""),
		"content": content,
		"published": 1,
		"allow_guest": 1,
		"_images": sorted(images),
		"_source": str(path),
	}


class Site:
	def __init__(self, url: str, key: str, secret: str):
		self.url = url.rstrip("/")
		self.auth = f"token {key}:{secret}"

	def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
		data = json.dumps(payload).encode() if payload is not None else None
		request = urllib.request.Request(f"{self.url}{path}", data=data, method=method)
		request.add_header("Authorization", self.auth)
		request.add_header("Accept", "application/json")
		request.add_header("User-Agent", USER_AGENT)
		if data:
			request.add_header("Content-Type", "application/json")
		try:
			with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
				return json.loads(response.read() or b"{}")
		except urllib.error.HTTPError as error:
			body = error.read().decode(errors="replace")[:400]
			if CLOUDFLARE_BLOCK in body:
				raise PublishError(
					"Cloudflare answered instead of the site (error 1010). Pass the origin "
					"with --url, the way scripts/golden_drill.py documents for the same reason."
				) from error
			raise PublishError(f"{method} {path} -> {error.code}: {body}") from error

	def existing(self) -> dict[str, dict]:
		"""Every Wiki Page on the site, by route."""
		fields = urllib.parse.quote(json.dumps(["name", "route", "title", "content"]))
		out = self._request("GET", f"/api/resource/Wiki Page?fields={fields}&limit_page_length=0")
		return {row["route"]: row for row in out.get("data", [])}

	def create(self, page: dict) -> None:
		self._request("POST", "/api/resource/Wiki Page", page)

	def update(self, name: str, page: dict) -> None:
		self._request("PUT", f"/api/resource/Wiki Page/{urllib.parse.quote(name)}", page)

	def has_file(self, path: str) -> bool:
		request = urllib.request.Request(
			f"{self.url}{urllib.parse.quote(path)}", method="HEAD", headers={"User-Agent": USER_AGENT}
		)
		try:
			with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
				return response.status == 200
		except urllib.error.HTTPError as error:
			if error.code == 403:
				raise PublishError(
					f"the edge refused {path} (403) — the file store was never reached"
				) from error
			return False
		except OSError:
			return False


def main() -> int:
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("--url", default=os.environ.get("DOCS_URL", DEFAULT_URL))
	parser.add_argument("--publish", action="store_true", help="write; without it this is a dry run")
	parser.add_argument("--check-images", action="store_true", help="HEAD every referenced image")
	parser.add_argument("--only", help="publish one route substring, for a single-page fix")
	args = parser.parse_args()

	key, secret = os.environ.get("DOCS_API_KEY"), os.environ.get("DOCS_API_SECRET")
	if not key or not secret:
		print("DOCS_API_KEY and DOCS_API_SECRET must be set (a docs-site key with Wiki Page write).")
		return 2

	pages = [page_payload(p) for p in sorted(DOCS_DIR.rglob("*.mdx"))]
	if args.only:
		pages = [p for p in pages if args.only in p["route"]]
		if not pages:
			print(f"No page matched --only {args.only!r}")
			return 1

	site = Site(args.url, key, secret)
	live = site.existing()
	print(f"{len(pages)} local pages, {len(live)} live pages on {site.url}\n")

	if args.check_images:
		# A referenced image that is not in the store publishes a broken page. Say so before
		# writing, not after: the store is on the docs site and is not fed by this repo.
		referenced = sorted({image for page in pages for image in page["_images"]})
		missing = [image for image in referenced if not site.has_file(image)]
		print(f"images referenced: {len(referenced)}, missing from the store: {len(missing)}")
		for image in missing:
			print(f"  MISSING  {image}")
		print()

	created = updated = unchanged = 0
	for page in sorted(pages, key=lambda p: p["route"]):
		route, source = page["route"], page.pop("_source")
		page.pop("_images")
		current = live.get(route)
		if current is None:
			created += 1
			print(f"  CREATE   {route}")
			if args.publish:
				site.create(page)
		elif (current.get("content") or "") != page["content"] or current.get("title") != page["title"]:
			updated += 1
			print(f"  UPDATE   {route}  ({source})")
			if args.publish:
				site.update(current["name"], page)
		else:
			unchanged += 1

	orphans = sorted(set(live) - {p["route"] for p in pages})
	print(f"\ncreated {created}, updated {updated}, unchanged {unchanged}")
	if orphans and not args.only:
		# Never deleted: this repo may not be the only thing that put a page there.
		print(f"{len(orphans)} live page(s) have no .mdx behind them, left alone:")
		for route in orphans:
			print(f"  ORPHAN   {route}")
	if not args.publish:
		print("\nDry run. Nothing was written. Re-run with --publish.")
	return 0


if __name__ == "__main__":
	try:
		sys.exit(main())
	except PublishError as error:
		print(f"error: {error}", file=sys.stderr)
		sys.exit(1)
