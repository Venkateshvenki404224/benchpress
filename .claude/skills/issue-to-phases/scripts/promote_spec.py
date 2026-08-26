#!/usr/bin/env python3
"""Create the specs/ tree and move specs between status buckets, in lockstep.

A spec's status lives in three places that must agree: the bucket folder it sits
in, its README banner, and its row plus counts in STATUS.md. Doing that by hand
is three edits and two counter updates, and it is reliably the step an agent
skips when it is concentrating on code — which leaves a shipped feature filed
under "not started".

This does all of it in one idempotent command, and `--check` verifies the three
agree without changing anything, so a loop can gate on it.

    promote_spec.py --init                        # create specs/, all buckets, STATUS.md
    promote_spec.py <slug> --to in-progress --detail "P1 started"
    promote_spec.py <slug> --to completed --detail "all phases in version-16 (PR #157)"
    promote_spec.py <slug> --check

Any run that files a spec also creates whatever part of the tree is missing, so a
repo that has never used specs/ — or one missing a bucket it has never needed —
needs no setup step.

Exit codes: 0 success or in sync, 1 usage/not-found, 2 --check found drift.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

BUCKETS = {
	"not-completed": ("Not started", "⬜ Not started", "spec authored, no implementation yet"),
	"in-progress": ("In progress", "🟡 In progress", "implementation started"),
	"completed": ("Completed", "✅ Completed", "all phases merged"),
	"superseded": ("Superseded", "⏹️ Superseded", "replaced by a later spec"),
}

# Forward only. Superseded is a manual sideways move from anywhere, so it is not
# listed as a successor — the guard exists to catch a spec being filed backwards,
# not to police an abandonment.
FORWARD = {"not-completed": 1, "in-progress": 2, "completed": 3}

BANNER_RE = re.compile(r"^>\s*\*\*Status:\*\*.*$", re.M)
COUNT_RE = re.compile(r"^Count:\s*\d+\s*$", re.M)
TOTALS_RE = re.compile(r"^Totals:.*$", re.M)
EMPTY_MARKER = "_None._"


STATUS_HEADER = """# Spec status

Tracks every feature spec under `specs/`, bucketed by implementation state.
A feature moves forward only: `not-completed/` → `in-progress/` →
`completed/` (or sideways to `superseded/` if abandoned). Keep this file, the
folder's location, and its README status banner in lockstep.
"""


def die(message: str, code: int = 1) -> None:
	print(f"error: {message}", file=sys.stderr)
	raise SystemExit(code)


def ensure_tree(specs_dir: Path) -> list[str]:
	"""Create specs/, every bucket, and STATUS.md. Returns what was created."""
	created = []
	if not specs_dir.exists():
		specs_dir.mkdir(parents=True)
		created.append(f"{specs_dir}/")
	for bucket in BUCKETS:
		d = specs_dir / bucket
		if not d.is_dir():
			d.mkdir(parents=True, exist_ok=True)
			created.append(f"{specs_dir}/{bucket}/")
		# Buckets are often empty for a while, and an empty directory does not
		# survive a clone. .gitkeep costs nothing and keeps the shape visible.
		keep = d / ".gitkeep"
		if not any(d.iterdir()):
			keep.touch(exist_ok=True)

	status_path = specs_dir / "STATUS.md"
	if not status_path.exists():
		body = STATUS_HEADER
		for _bucket, (heading, _, _) in BUCKETS.items():
			body += f"\n## {heading}\n" + render_section([])
		body += (
			"\n---\n\nTotals: 0 specs tracked (0 not started, 0 in progress, 0 completed, 0 superseded).\n"
		)
		status_path.write_text(body)
		created.append(f"{status_path}")
	else:
		# An existing STATUS.md may predate a bucket. Add any missing section so
		# section_bounds() never dies on a tree this script just finished creating.
		text = status_path.read_text()
		added = False
		for _bucket, (heading, _, _) in BUCKETS.items():
			if not re.search(rf"^##\s+{re.escape(heading)}\s*$", text, re.M):
				insert_at = TOTALS_RE.search(text)
				section = f"\n## {heading}\n" + render_section([])
				if insert_at:
					cut = text.rfind("---", 0, insert_at.start())
					cut = cut if cut != -1 else insert_at.start()
					text = text[:cut] + section + "\n" + text[cut:]
				else:
					text = text.rstrip() + "\n" + section
				added = True
				created.append(f"{status_path} '## {heading}' section")
		if added:
			status_path.write_text(text)
	return created


def find_spec(specs_dir: Path, slug: str) -> tuple[str, Path]:
	for bucket in BUCKETS:
		candidate = specs_dir / bucket / slug
		if candidate.is_dir():
			return bucket, candidate
	die(f"no spec folder named {slug!r} under {specs_dir}/<bucket>/")


def section_bounds(text: str, heading: str) -> tuple[int, int]:
	"""Character range of one `## <heading>` section, excluding the next heading."""
	start = re.search(rf"^##\s+{re.escape(heading)}\s*$", text, re.M)
	if not start:
		die(f"STATUS.md has no '## {heading}' section")
	nxt = re.search(r"^(##\s+|---\s*$)", text[start.end() :], re.M)
	end = start.end() + (nxt.start() if nxt else len(text) - start.end())
	return start.end(), end


def row_slug(row: str) -> str | None:
	m = re.match(r"\|\s*\[([^\]]+)\]", row)
	return m.group(1) if m else None


def split_rows(block: str) -> tuple[list[str], list[str]]:
	"""Separate table data rows from everything else in a section."""
	rows, other = [], []
	for line in block.splitlines():
		s = line.strip()
		if s.startswith("|") and not re.match(r"\|\s*-{2,}", s) and not s.startswith("| Feature"):
			rows.append(s)
		else:
			other.append(line)
	return rows, other


def render_section(rows: list[str]) -> str:
	if not rows:
		return f"\n{EMPTY_MARKER}\n\nCount: 0\n"
	body = "\n".join(rows)
	return f"\n| Feature | Notes |\n|---|---|\n{body}\n\nCount: {len(rows)}\n"


def read_row(text: str, slug: str) -> tuple[str | None, str | None]:
	"""Return (bucket, note) for the slug's existing STATUS.md row, if any."""
	for bucket, (heading, _, _) in BUCKETS.items():
		lo, hi = section_bounds(text, heading)
		for row in split_rows(text[lo:hi])[0]:
			if row_slug(row) == slug:
				parts = [p.strip() for p in row.strip("|").split("|")]
				return bucket, (parts[1] if len(parts) > 1 else "")
	return None, None


def update_status(status_path: Path, slug: str, target: str, note: str | None) -> str:
	text = status_path.read_text()
	_, existing_note = read_row(text, slug)
	note = note or existing_note or BUCKETS[target][2]
	new_row = f"| [{slug}]({target}/{slug}/README.md) | {note} |"

	counts: dict[str, int] = {}
	for bucket, (heading, _, _) in BUCKETS.items():
		lo, hi = section_bounds(text, heading)
		rows = [r for r in split_rows(text[lo:hi])[0] if row_slug(r) != slug]
		if bucket == target:
			rows.append(new_row)
		counts[bucket] = len(rows)
		text = text[:lo] + render_section(rows) + text[hi:]

	total = sum(counts.values())
	totals = (
		f"Totals: {total} specs tracked ({counts['not-completed']} not started, "
		f"{counts['in-progress']} in progress, {counts['completed']} completed, "
		f"{counts['superseded']} superseded)."
	)
	if TOTALS_RE.search(text):
		text = TOTALS_RE.sub(totals, text, count=1)
	else:
		text = text.rstrip() + f"\n\n---\n\n{totals}\n"

	status_path.write_text(text)
	return note


def set_banner(readme: Path, target: str, detail: str | None) -> str:
	label = BUCKETS[target][1]
	banner = f"> **Status:** {label} — {detail or BUCKETS[target][2]}"
	text = readme.read_text() if readme.exists() else ""
	if BANNER_RE.search(text):
		text = BANNER_RE.sub(banner, text, count=1)
	else:
		text = f"{banner}\n\n{text}"
	readme.write_text(text)
	return banner


def check(specs_dir: Path, slug: str) -> int:
	bucket, folder = find_spec(specs_dir, slug)
	status_path = specs_dir / "STATUS.md"
	problems = []

	readme = folder / "README.md"
	if not readme.exists():
		problems.append("README.md is missing")
	else:
		m = BANNER_RE.search(readme.read_text())
		if not m:
			problems.append("README.md has no status banner")
		elif BUCKETS[bucket][1] not in m.group(0):
			problems.append(f"banner says {m.group(0).strip()!r} but the folder is in {bucket}/")

	if not status_path.exists():
		problems.append("STATUS.md is missing")
	else:
		text = status_path.read_text()
		row_bucket, _ = read_row(text, slug)
		if row_bucket is None:
			problems.append(f"STATUS.md has no row for {slug}")
		elif row_bucket != bucket:
			problems.append(f"STATUS.md files it under {row_bucket} but the folder is in {bucket}/")
		for _b, (heading, _, _) in BUCKETS.items():
			lo, hi = section_bounds(text, heading)
			block = text[lo:hi]
			rows, _ = split_rows(block)
			declared = COUNT_RE.search(block)
			if declared and int(declared.group(0).split(":")[1]) != len(rows):
				problems.append(f"'{heading}' says {declared.group(0).strip()} but lists {len(rows)} rows")

	if problems:
		print(f"{slug}: OUT OF SYNC")
		for p in problems:
			print(f"  - {p}")
		return 2
	print(f"{slug}: in sync — folder {bucket}/, banner and STATUS.md agree")
	return 0


def main() -> int:
	ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	ap.add_argument("slug", nargs="?", help="the spec folder name, e.g. wildcard-cert-routing")
	ap.add_argument("--to", choices=sorted(BUCKETS), help="bucket to move into")
	ap.add_argument("--detail", help="text after the em dash in the README banner")
	ap.add_argument("--note", help="the Notes cell in STATUS.md (kept from the existing row if omitted)")
	ap.add_argument("--specs-dir", default="specs", help="path to specs/ (default: specs)")
	ap.add_argument("--check", action="store_true", help="verify the three trackers agree; change nothing")
	ap.add_argument(
		"--init", action="store_true", help="create specs/, every bucket and STATUS.md, then exit"
	)
	ap.add_argument("--force", action="store_true", help="allow a backwards move")
	args = ap.parse_args()

	specs_dir = Path(args.specs_dir)

	if args.init:
		created = ensure_tree(specs_dir)
		print("\n".join(f"created {c}" for c in created) if created else f"{specs_dir} tree already complete")
		return 0

	if not args.slug:
		die("a spec slug is required unless --init is given")

	if args.check:
		if not specs_dir.is_dir():
			die(f"{specs_dir} does not exist — run with --init first")
		return check(specs_dir, args.slug)
	if not args.to:
		die("--to is required unless --check or --init is given")

	# Filing a spec into a tree that does not exist yet should just work.
	ensure_tree(specs_dir)

	current, folder = find_spec(specs_dir, args.slug)
	if current != args.to and FORWARD.get(args.to, 99) < FORWARD.get(current, 0) and not args.force:
		die(
			f"{args.slug} is in {current}/ and {args.to}/ is backwards. "
			"A spec moves forward only; pass --force if this is a deliberate correction."
		)

	target_dir = specs_dir / args.to / args.slug
	if current != args.to:
		target_dir.parent.mkdir(parents=True, exist_ok=True)
		if target_dir.exists():
			die(f"{target_dir} already exists — resolve by hand")
		shutil.move(str(folder), str(target_dir))
		print(f"moved {current}/{args.slug} -> {args.to}/{args.slug}")
	else:
		print(f"{args.slug} already in {args.to}/ — reconciling banner and STATUS.md")

	print(f"banner: {set_banner(target_dir / 'README.md', args.to, args.detail)}")
	print(f"STATUS.md note: {update_status(specs_dir / 'STATUS.md', args.slug, args.to, args.note)}")
	return check(specs_dir, args.slug)


if __name__ == "__main__":
	raise SystemExit(main())
