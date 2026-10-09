# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import base64
import binascii
import hashlib

import frappe
from frappe import _

from benchpress.permissions import require_app_user

SSH_KEYS_FIELD = "bp_ssh_public_keys"
KEY_TYPES = (
	"ssh-ed25519",
	"ssh-rsa",
	"ecdsa-sha2-nistp256",
	"ecdsa-sha2-nistp384",
	"ecdsa-sha2-nistp521",
	"sk-ssh-ed25519@openssh.com",
)
MAX_KEYS = 10


@frappe.whitelist()
def list_ssh_keys() -> list[dict]:
	require_app_user()
	return [_row(line) for line in ssh_keys_of(frappe.session.user).splitlines() if line]


@frappe.whitelist(methods=["POST"])
def add_ssh_key(key: str) -> list[dict]:
	require_app_user()
	lines = [line.strip() for line in (key or "").splitlines() if line.strip()]
	pasted = [_valid_key(number, line) for number, line in enumerate(lines, 1)]
	if len(pasted) != 1:
		frappe.throw(_("Paste one key at a time."))
	saved = _locked_keys()
	if _key_fingerprint(pasted[0]) in {_key_fingerprint(line) for line in saved}:
		frappe.throw(_("That key is already saved."))
	if len(saved) >= MAX_KEYS:
		frappe.throw(_("You can save at most {0} SSH keys.").format(MAX_KEYS))
	return _save_keys([*saved, pasted[0]])


@frappe.whitelist(methods=["POST"])
def remove_ssh_key(fingerprint: str) -> list[dict]:
	require_app_user()
	saved = _locked_keys()
	kept = [line for line in saved if _key_fingerprint(line) != fingerprint]
	if len(kept) == len(saved):
		frappe.throw(_("That key is not saved."))
	return _save_keys(kept)


def ssh_keys_of(email: str) -> str:
	return frappe.db.get_value("User", email, SSH_KEYS_FIELD) or ""


class BenchPressPasswordResetMixin:
	def password_reset_mail(self, link):
		# Not the framework's own mail: `send_login_mail` forces `with_container`, which draws a
		# white masthead from `app_logo_url` and signs the body with whoever was logged in. An
		# operator who named a template in System Settings still gets theirs.
		if frappe.db.get_system_setting("reset_password_template"):
			return super().password_reset_mail(link)

		# Imported here: this mixin is loaded by `get_controller`, which runs before a request has
		# a reason to pull the mail module's own import chain in.
		from benchpress import emails

		emails.send_password_reset(self, link)


def _valid_key(number: int, line: str) -> str:
	if "PRIVATE KEY" in line:
		frappe.throw(_("Line {0} is a private key. Paste the .pub file instead.").format(number))
	parts = line.split(None, 2)
	if len(parts) < 2 or parts[0] not in KEY_TYPES or _blob_type(parts[1]) != parts[0]:
		frappe.throw(_("Line {0} is not an SSH public key.").format(number))
	return " ".join(parts)


def _blob_type(encoded: str) -> str | None:
	try:
		blob = base64.b64decode(encoded, validate=True)
	except binascii.Error:
		return None
	length = int.from_bytes(blob[:4], "big")
	if len(blob) < 4 + length:
		return None
	return blob[4 : 4 + length].decode("ascii", errors="replace")


def _locked_keys() -> list[str]:
	stored = frappe.db.get_value("User", frappe.session.user, SSH_KEYS_FIELD, for_update=True) or ""
	return [line for line in stored.splitlines() if line]


def _save_keys(keys: list[str]) -> list[dict]:
	frappe.db.set_value("User", frappe.session.user, SSH_KEYS_FIELD, "\n".join(keys))
	return [_row(line) for line in keys]


def _row(line: str) -> dict:
	kind, encoded, *comment = line.split(None, 2)
	return {"fingerprint": _blob_fingerprint(encoded), "type": kind, "comment": comment[0] if comment else ""}


def _key_fingerprint(line: str) -> str:
	return _blob_fingerprint(line.split()[1])


def _blob_fingerprint(encoded: str) -> str:
	digest = hashlib.sha256(base64.b64decode(encoded)).digest()
	return "SHA256:" + base64.b64encode(digest).decode().rstrip("=")
