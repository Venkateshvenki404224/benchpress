#!/usr/bin/env python3
"""Create or remove the demo Labs and users the documentation screenshots are taken from.

`--destroy` removes only what this script creates, and refuses every other name.
"""

from __future__ import annotations

import argparse
import json
import re
import secrets
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
DEVOPS_DIR = APP_DIR.parents[1]
ENV_FILE = DEVOPS_DIR / ".env"
PASSWORD_KEY = "DOCS_DEMO_PASSWORD"
CACHE_REPOSITORY = "benchpress"

# Deploy never builds. `deploy_manager._prepare_lab_image` demands an image named
# `benchpress/<lab_id>:lab` and throws otherwise, so each demo lab borrows the image of a lab
# that already has one, under a second tag. A tag is a pointer: no layers, no build, no disk.
# `source_lab` also supplies the app rows, so the lab always describes the image it runs.
DEMO_LABS = {
	"crm-demo": {
		"source_lab": "crm",
		"title": "Frappe CRM demo",
		"description": "Frappe CRM on version-15 - the lab the documentation deploys from.",
		"instance_size": "Small",
	},
	"erpnext-training": {
		"source_lab": "erpnext",
		"title": "ERPNext training",
		"description": "ERPNext on version-15 - a throwaway bench for training exercises.",
		"instance_size": "Medium",
	},
	"helpdesk-sandbox": {
		"source_lab": "client-frappe-16",
		"title": "Helpdesk sandbox",
		"description": "The full client stack, Frappe Helpdesk included - the bench the docs stop and start.",
		"instance_size": "Medium",
	},
}

DEMO_USERS = {
	"demo@benchpress.cloud": {"first_name": "Demo", "last_name": "Admin", "role": "BenchPress Admin"},
	"intern@benchpress.cloud": {"first_name": "Sam", "last_name": "Intern", "role": "BenchPress User"},
}

LAB_OWNER = "demo@benchpress.cloud"

# Every bench command goes to queue-long. It is the only service with the writable Traefik
# mount, so a teardown run anywhere else deletes a route file it cannot put back.
BENCH_SERVICE = "queue-long"

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def lab_image(lab_id: str) -> str:
	"""`image_cache.cache_tag`, restated here because this script runs outside the bench."""
	return f"{CACHE_REPOSITORY}/{lab_id}:lab"


class Bench:
	"""Runs Python inside the site. The console is the only shell this deployment has."""

	def run(self, body: str, payload: dict) -> list[str]:
		"""One `exec` with its own namespace: the console ends a block at a blank line, and a
		generator expression there cannot read the caller's locals."""
		script = f"exec({body!r}, {{'payload': {json.dumps(payload)!r}}})\n"
		result = subprocess.run(
			["docker", "compose", "exec", "-T", BENCH_SERVICE, "bench", "--site", "frontend", "console"],
			cwd=DEVOPS_DIR,
			input=script,
			text=True,
			capture_output=True,
		)
		clean = ANSI.sub("", result.stdout)
		# Not anchored: the console prints its `In [1]:` prompt on the same line as the result.
		reported = re.search(r"SEED_RESULT (.+)$", clean, re.M)
		if not reported:
			sys.stderr.write(clean[-4000:] + result.stderr[-2000:])
			raise SystemExit("the site refused the script - its output is above")
		return json.loads(reported.group(1))


class Images:
	"""The tag aliases that let a demo lab deploy from an image built for another lab."""

	def alias(self, source: str, tag: str) -> str | None:
		if not self.image_id(source):
			raise SystemExit(f"no image {source} on this host - build it, or edit DEMO_LABS")
		if self.image_id(tag) == self.image_id(source):
			return None
		subprocess.run(["docker", "tag", source, tag], check=True)
		return f"CHANGE tagged {tag} from {source}"

	def unalias(self, source: str, tag: str) -> str | None:
		"""Drop the alias only while it still points at the borrowed image, never a real one."""
		tag_id = self.image_id(tag)
		if not tag_id:
			return None
		if tag_id != self.image_id(source):
			return f"FAIL refused to untag {tag} - it no longer points at {source}"
		subprocess.run(["docker", "rmi", tag], check=True, capture_output=True)
		return f"CHANGE untagged {tag}"

	def image_id(self, tag: str) -> str:
		result = subprocess.run(
			["docker", "image", "inspect", "-f", "{{.Id}}", tag], capture_output=True, text=True
		)
		return result.stdout.strip() if result.returncode == 0 else ""


DESTROY_BODY = """
import json

import frappe
from benchpress import api

payload = json.loads(payload)
changes = []
for lab_id in payload["labs"]:
	for bench in frappe.get_all("Bench Instance", filters={"lab": lab_id}, pluck="name"):
		api.bench_action(bench, "delete")
		changes.append("CHANGE deleted bench " + bench)
	if frappe.db.exists("Lab", lab_id):
		frappe.delete_doc("Lab", lab_id, force=True)
		changes.append("CHANGE deleted lab " + lab_id)
	else:
		changes.append("SAME no lab " + lab_id)
for email in payload["users"]:
	if not frappe.db.exists("User", email):
		changes.append("SAME no user " + email)
		continue
	try:
		frappe.delete_doc("User", email, force=True)
		changes.append("CHANGE deleted user " + email)
	except Exception as error:
		frappe.db.rollback()
		changes.append("FAIL kept user " + email + " - " + str(error)[:120].replace(chr(10), " "))
frappe.db.commit()
print("SEED" + "_RESULT", json.dumps(changes))
"""

CREATE_BODY = """
import json

import frappe

payload = json.loads(payload)
changes = []
for email, person in payload["users"].items():
	fresh = not frappe.db.exists("User", email)
	if fresh:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": person["first_name"],
				"last_name": person["last_name"],
				"user_type": "System User",
				"send_welcome_email": 0,
				"enabled": 1,
			}
		)
		user.insert(ignore_permissions=True)
		changes.append("CHANGE created user " + email)
	else:
		user = frappe.get_doc("User", email)
		changes.append("SAME user " + email)
	if not [row for row in user.roles if row.role == person["role"]]:
		user.append("roles", {"role": person["role"]})
		user.save(ignore_permissions=True)
		changes.append("CHANGE granted " + person["role"] + " to " + email)
	if fresh or payload["reset_password"]:
		user.new_password = payload["password"]
		user.save(ignore_permissions=True)
		changes.append("CHANGE set password for " + email)
for lab_id, spec in payload["labs"].items():
	if frappe.db.exists("Lab", lab_id):
		changes.append("SAME lab " + lab_id)
		continue
	source = frappe.get_doc("Lab", spec["source_lab"])
	# The docs say these labs came from the catalog, so the record has to say so too.
	template = spec["source_lab"] if frappe.db.exists("Lab Template", spec["source_lab"]) else None
	lab = frappe.get_doc(
		{
			"doctype": "Lab",
			"lab_id": lab_id,
			"title": spec["title"],
			"description": spec["description"],
			"template": template,
			"frappe_version": source.frappe_version,
			"instance_size": spec["instance_size"],
			"memory_limit": source.memory_limit,
			"cpu_cores": source.cpu_cores,
			"image_tag": spec["image_tag"],
			"status": "Ready",
			"enable_ssh": 1,
			"enable_code_server": 1,
			"apps": [
				{
					"app_name": row.app_name,
					"app_label": row.app_label,
					"git_url": row.git_url,
					"branch": row.branch,
				}
				for row in source.apps
			],
		}
	)
	lab.owner = payload["lab_owner"]
	lab.insert(ignore_permissions=True)
	changes.append("CHANGE created lab " + lab_id)
frappe.db.commit()
print("SEED" + "_RESULT", json.dumps(changes))
"""


def create(reset_password: bool) -> list[str]:
	images = Images()
	changes = []
	labs = {}
	for lab_id, spec in DEMO_LABS.items():
		tag = lab_image(lab_id)
		note = images.alias(lab_image(spec["source_lab"]), tag)
		changes.append(note or f"SAME image {tag}")
		labs[lab_id] = dict(spec, image_tag=tag)
	payload = {
		"labs": labs,
		"users": DEMO_USERS,
		"lab_owner": LAB_OWNER,
		"password": read_or_make_password(),
		"reset_password": reset_password,
	}
	return changes + Bench().run(CREATE_BODY, payload)


def destroy(lab_ids: list[str]) -> list[str]:
	changes = Bench().run(DESTROY_BODY, {"labs": lab_ids, "users": list(DEMO_USERS)})
	images = Images()
	for lab_id in lab_ids:
		note = images.unalias(lab_image(DEMO_LABS[lab_id]["source_lab"]), lab_image(lab_id))
		if note:
			changes.append(note)
	return changes


def read_or_make_password() -> str:
	"""One password for both demo users, kept in .env - a credential in tracked source is public."""
	text = ENV_FILE.read_text() if ENV_FILE.exists() else ""
	found = re.search(rf"^{PASSWORD_KEY}=(.+)$", text, re.M)
	if found:
		return found.group(1).strip()
	password = secrets.token_urlsafe(18)
	with ENV_FILE.open("a") as handle:
		handle.write("\n# Demo logins for the documentation screenshots (scripts/seed_docs_demo.py)\n")
		handle.write(f"{PASSWORD_KEY}={password}\n")
	return password


def main() -> int:
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("--destroy", action="store_true", help="remove the demo records instead")
	parser.add_argument("--lab", action="append", default=[], help="limit --destroy to this lab; repeatable")
	parser.add_argument("--reset-password", action="store_true", help="rewrite both demo users' passwords")
	args = parser.parse_args()

	if args.lab and not args.destroy:
		print("--lab only narrows --destroy", file=sys.stderr)
		return 2

	if args.destroy:
		targets = args.lab or list(DEMO_LABS)
		strangers = [name for name in targets if name not in DEMO_LABS]
		if strangers:
			print(
				f"refusing to destroy {', '.join(strangers)}: this script owns only {', '.join(DEMO_LABS)}",
				file=sys.stderr,
			)
			return 1
		changes = destroy(targets)
	else:
		changes = create(args.reset_password)

	for line in changes:
		print(line)
	made = [line for line in changes if line.startswith("CHANGE")]
	failed = [line for line in changes if line.startswith("FAIL")]
	print(f"{len(made)} change(s), {len(changes) - len(made) - len(failed)} already correct")
	return 1 if failed else 0


if __name__ == "__main__":
	sys.exit(main())
