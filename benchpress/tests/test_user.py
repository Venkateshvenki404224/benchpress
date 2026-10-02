# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import frappe
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from frappe.tests import IntegrationTestCase

from benchpress import user
from benchpress.tests.fixtures import drop

OWNER = "user-keys-owner@example.com"
BYSTANDER = "user-keys-bystander@example.com"

ED25519 = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGmGY6wbhu8fIW8Ss6S9Yq5Vs9esVwGK0lP9CmjKHuPv dev@laptop"
RSA = (
	"ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAAgQDFF3bfYbZTa1Nj2/ie357K3VlE2c4YKsTB6utNJm9lNUqy3nwqyizl0Nw6/nJnQI9CWI2t"
	"V8+p3YNqVGc+IbmixQqOEP0mXHGeMUgp7qjZlAnvKnk8njpDGvhE9Wq1BDVIl7tGNNU7qRgEFCwSfUN1SnVgHcwKRlDLoUy097/vmw=="
)
ED25519_FINGERPRINT = "SHA256:azc4Qc3RUbB63tfNAI4eRP/Bz/Fin7oPOwPKBrejxGk"
RSA_FINGERPRINT = "SHA256:0BXSTa/ZJm5+6zmrW1yE9DGMkYbOnScPAT9ivh90sHI"


def _app_user(email):
	drop("User", email)
	frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": "Keys",
			"send_welcome_email": 0,
			"roles": [{"role": "BenchPress User"}],
		}
	).insert(ignore_permissions=True)


class TestSshKeys(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		for email in (OWNER, BYSTANDER):
			_app_user(email)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for email in (OWNER, BYSTANDER):
			drop("User", email)
		super().tearDownClass()

	def setUp(self):
		frappe.set_user(OWNER)
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(frappe.db.rollback)

	def test_keys_are_stored_as_pasted_one_per_line(self):
		user.add_ssh_key(ED25519)
		user.add_ssh_key(f"\n{RSA}\n")

		self.assertEqual(user.ssh_keys_of(OWNER), f"{ED25519}\n{RSA}")

	def test_a_row_names_the_key_by_the_fingerprint_ssh_keygen_prints(self):
		(row,) = user.add_ssh_key(ED25519)

		self.assertEqual(row["fingerprint"], ED25519_FINGERPRINT)

	def test_an_rsa_row_names_its_key_the_same_way(self):
		user.add_ssh_key(ED25519)

		self.assertEqual(
			[row["fingerprint"] for row in user.add_ssh_key(RSA)], [ED25519_FINGERPRINT, RSA_FINGERPRINT]
		)

	def test_no_row_carries_the_key_body(self):
		user.add_ssh_key(ED25519)
		user.add_ssh_key(RSA)

		listed = str(user.list_ssh_keys())
		for key in (ED25519, RSA):
			self.assertNotIn(key.split()[1], listed)

	def test_a_row_keeps_the_comment_and_type_as_saved(self):
		user.add_ssh_key(ED25519)
		user.add_ssh_key(RSA)

		self.assertEqual(
			[(row["type"], row["comment"]) for row in user.list_ssh_keys()],
			[("ssh-ed25519", "dev@laptop"), ("ssh-rsa", "")],
		)

	def test_the_same_key_under_another_comment_is_refused(self):
		user.add_ssh_key(ED25519)

		with self.assertRaisesRegex(frappe.ValidationError, "already saved"):
			user.add_ssh_key(ED25519.replace("dev@laptop", "dev@desktop"))

		self.assertEqual(user.ssh_keys_of(OWNER), ED25519)

	def test_a_blank_line_in_the_saved_keys_is_skipped(self):
		frappe.db.set_value("User", OWNER, user.SSH_KEYS_FIELD, f"{ED25519}\n\n")

		user.add_ssh_key(RSA)

		self.assertEqual(user.ssh_keys_of(OWNER), f"{ED25519}\n{RSA}")

	def test_two_keys_in_one_paste_are_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Paste one key at a time."):
			user.add_ssh_key(f"{ED25519}\n{RSA}")

		self.assertEqual(user.list_ssh_keys(), [])

	def test_an_eleventh_key_is_refused(self):
		for number in range(user.MAX_KEYS):
			user.add_ssh_key(_fresh_key(f"key-{number}"))

		with self.assertRaisesRegex(frappe.ValidationError, "at most 10"):
			user.add_ssh_key(ED25519)

		self.assertEqual(len(user.list_ssh_keys()), user.MAX_KEYS)
		self.assertNotIn(ED25519_FINGERPRINT, str(user.list_ssh_keys()))

	def test_a_private_key_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Line 1 is a private key"):
			user.add_ssh_key("-----BEGIN OPENSSH PRIVATE KEY-----")

	def test_a_private_key_after_a_public_one_is_named(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Line 2 is a private key"):
			user.add_ssh_key(f"{ED25519}\n-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEAAAAA")

	def test_a_pasted_private_key_file_is_named_as_one_before_the_key_count(self):
		pem = "\n".join(["-----BEGIN OPENSSH PRIVATE KEY-----", *["b3BlbnNzaC1rZXktdjEAAAAA"] * 30])

		with self.assertRaisesRegex(frappe.ValidationError, "Line 1 is a private key"):
			user.add_ssh_key(pem)

	def test_an_unknown_key_type_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Line 1 is not an SSH public key"):
			user.add_ssh_key(ED25519.replace("ssh-ed25519", "ssh-dss"))

	def test_a_type_that_disagrees_with_its_blob_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Line 1 is not an SSH public key"):
			user.add_ssh_key(ED25519.replace("ssh-ed25519", "ssh-rsa"))

	def test_authorized_keys_options_are_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Line 1 is not an SSH public key"):
			user.add_ssh_key(f'command="/bin/sh" {ED25519}')

	def test_a_refused_add_keeps_the_saved_keys(self):
		user.add_ssh_key(ED25519)

		with self.assertRaises(frappe.ValidationError):
			user.add_ssh_key("not a key")

		self.assertEqual(user.ssh_keys_of(OWNER), ED25519)

	def test_an_add_writes_the_callers_row_and_nobody_elses(self):
		frappe.set_user(BYSTANDER)
		user.add_ssh_key(RSA)
		frappe.set_user(OWNER)

		user.add_ssh_key(ED25519)

		self.assertEqual(user.ssh_keys_of(OWNER), ED25519)
		self.assertEqual(user.ssh_keys_of(BYSTANDER), RSA)

	def test_a_remove_drops_the_named_key_and_keeps_the_other(self):
		user.add_ssh_key(ED25519)
		user.add_ssh_key(RSA)

		rows = user.remove_ssh_key(ED25519_FINGERPRINT)

		self.assertEqual([row["fingerprint"] for row in rows], [RSA_FINGERPRINT])
		self.assertEqual(user.ssh_keys_of(OWNER), RSA)

	def test_a_remove_skips_a_blank_line_in_the_saved_keys(self):
		frappe.db.set_value("User", OWNER, user.SSH_KEYS_FIELD, f"{ED25519}\n\n{RSA}")

		user.remove_ssh_key(RSA_FINGERPRINT)

		self.assertEqual(user.ssh_keys_of(OWNER), ED25519)

	def test_a_remove_of_a_key_that_is_not_saved_is_refused(self):
		user.add_ssh_key(ED25519)

		with self.assertRaisesRegex(frappe.ValidationError, "That key is not saved."):
			user.remove_ssh_key(RSA_FINGERPRINT)

		self.assertEqual(user.ssh_keys_of(OWNER), ED25519)

	def test_a_remove_leaves_everybody_elses_keys_alone(self):
		frappe.set_user(BYSTANDER)
		user.add_ssh_key(ED25519)
		frappe.set_user(OWNER)
		user.add_ssh_key(ED25519)

		user.remove_ssh_key(ED25519_FINGERPRINT)

		self.assertEqual(user.ssh_keys_of(OWNER), "")
		self.assertEqual(user.ssh_keys_of(BYSTANDER), ED25519)

	def test_a_guest_can_neither_list_add_nor_remove_keys(self):
		frappe.set_user("Guest")

		with self.assertRaises(frappe.PermissionError):
			user.list_ssh_keys()
		with self.assertRaises(frappe.PermissionError):
			user.add_ssh_key(ED25519)
		with self.assertRaises(frappe.PermissionError):
			user.remove_ssh_key(ED25519_FINGERPRINT)

	def test_the_whole_text_endpoints_are_gone(self):
		for verb in ("get", "set"):
			self.assertFalse(hasattr(user, f"{verb}_ssh_keys"))


def _fresh_key(comment):
	public = Ed25519PrivateKey.generate().public_key()
	return f"{public.public_bytes(Encoding.OpenSSH, PublicFormat.OpenSSH).decode()} {comment}"
