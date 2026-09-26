# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import frappe
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

	def test_an_ed25519_key_saves(self):
		self.assertEqual(user.set_ssh_keys(ED25519), ED25519)
		self.assertEqual(user.get_ssh_keys(), ED25519)

	def test_an_rsa_key_saves_beside_an_ed25519_key(self):
		self.assertEqual(user.set_ssh_keys(f"{ED25519}\n\n{RSA}\n"), f"{ED25519}\n{RSA}")

	def test_a_private_key_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Line 2 is a private key"):
			user.set_ssh_keys(f"{ED25519}\n-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEAAAAA")

	def test_a_long_private_key_is_named_as_one_before_the_key_count(self):
		pem = "\n".join(["-----BEGIN OPENSSH PRIVATE KEY-----", *["b3BlbnNzaC1rZXktdjEAAAAA"] * 30])

		with self.assertRaisesRegex(frappe.ValidationError, "Line 1 is a private key"):
			user.set_ssh_keys(pem)

	def test_an_unknown_key_type_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Line 1 is not an SSH public key"):
			user.set_ssh_keys(ED25519.replace("ssh-ed25519", "ssh-dss"))

	def test_a_type_that_disagrees_with_its_blob_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Line 1 is not an SSH public key"):
			user.set_ssh_keys(ED25519.replace("ssh-ed25519", "ssh-rsa"))

	def test_authorized_keys_options_are_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Line 1 is not an SSH public key"):
			user.set_ssh_keys(f'command="/bin/sh" {ED25519}')

	def test_an_eleventh_key_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "at most 10"):
			user.set_ssh_keys("\n".join(f"{ED25519} {n}" for n in range(11)))

	def test_a_refused_save_keeps_the_saved_keys(self):
		user.set_ssh_keys(ED25519)

		with self.assertRaises(frappe.ValidationError):
			user.set_ssh_keys("not a key")

		self.assertEqual(user.get_ssh_keys(), ED25519)

	def test_a_save_writes_the_callers_row_and_nobody_elses(self):
		user.set_ssh_keys(ED25519)

		frappe.set_user(BYSTANDER)
		self.assertEqual(user.get_ssh_keys(), "")

	def test_a_guest_can_neither_read_nor_write_keys(self):
		frappe.set_user("Guest")

		with self.assertRaises(frappe.PermissionError):
			user.get_ssh_keys()
		with self.assertRaises(frappe.PermissionError):
			user.set_ssh_keys(ED25519)
