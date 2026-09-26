# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import base64
import binascii

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
def get_ssh_keys() -> str:
	require_app_user()
	return ssh_keys_of(frappe.session.user)


@frappe.whitelist(methods=["POST"])
def set_ssh_keys(keys: str) -> str:
	require_app_user()
	lines = [(number, line.strip()) for number, line in enumerate((keys or "").splitlines(), 1)]
	clean = [_valid_key(number, line) for number, line in lines if line]
	if len(clean) > MAX_KEYS:
		frappe.throw(_("You can save at most {0} SSH keys.").format(MAX_KEYS))
	saved = "\n".join(clean)
	frappe.db.set_value("User", frappe.session.user, SSH_KEYS_FIELD, saved)
	return saved


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
