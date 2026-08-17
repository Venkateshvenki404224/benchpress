# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""`waitlist.join` is the first `allow_guest` method in the app, so it is tested as a boundary.

The assertions that matter are the ones about what the endpoint refuses to do: it must not tell a
stranger whether an address is already registered, it must not accept an address that is not one,
it must not let a single caller enumerate through it, and approving an entry must hand out exactly
one role — the least-privileged one — rather than whatever the inviter happens to hold.
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from benchpress import waitlist
from benchpress.benchpress.doctype.waitlist_entry.waitlist_entry import ACCESS_ROLE

EMAIL = "waitlist-test@example.com"
OTHER_EMAIL = "waitlist-other@example.com"


def _delete_entry(email):
	if frappe.db.exists("Waitlist Entry", email):
		frappe.delete_doc("Waitlist Entry", email, force=True, ignore_permissions=True)
	if frappe.db.exists("User", email):
		frappe.delete_doc("User", email, force=True, ignore_permissions=True)


class TestWaitlist(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self._silence_outgoing_mail()
		for email in (EMAIL, OTHER_EMAIL):
			_delete_entry(email)
			self.addCleanup(_delete_entry, email)
		self.addCleanup(frappe.set_user, "Administrator")

	def _silence_outgoing_mail(self) -> None:
		"""Approval creates a `User` with a welcome email, which must not leave the test.

		Muting alone is not enough: the send runs as an after-commit task, so on a site with no
		Email Account it raises `OutgoingEmailError` inside whichever *later* test commits first —
		which is how it failed in CI while passing on a dev site that has an account configured.
		Patching the send out means no queue row is ever written.
		"""
		# `None`, not a mock: `User.send_welcome_mail_to_user` reads `.message` off the returned
		# Email Queue document when there is one, and a mock's attribute is not a string.
		mailer = patch("frappe.sendmail", return_value=None)
		mailer.start()
		self.addCleanup(mailer.stop)
		self.addCleanup(setattr, frappe.flags, "mute_emails", frappe.flags.mute_emails)
		frappe.flags.mute_emails = True

	def test_a_valid_submission_creates_one_pending_row(self):
		response = waitlist.join(EMAIL, full_name="Test Person", company="Acme")

		self.assertTrue(response["joined"])
		entry = frappe.get_doc("Waitlist Entry", EMAIL)
		self.assertEqual(entry.status, "Pending")
		self.assertEqual(entry.full_name, "Test Person")
		self.assertIsNone(entry.approved_on)

	def test_a_duplicate_is_idempotent_and_says_nothing(self):
		first = waitlist.join(EMAIL, company="Acme")
		second = waitlist.join(EMAIL, company="Somewhere else")

		self.assertEqual(first, second, "the second answer discloses that the address is known")
		self.assertEqual(frappe.db.count("Waitlist Entry", {"email": EMAIL}), 1)
		self.assertEqual(frappe.db.get_value("Waitlist Entry", EMAIL, "company"), "Acme")

	def test_the_address_is_normalised_so_case_cannot_duplicate(self):
		waitlist.join(EMAIL.upper())
		self.assertTrue(frappe.db.exists("Waitlist Entry", EMAIL))

	def test_an_invalid_address_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			waitlist.join("not-an-address")
		self.assertEqual(frappe.db.count("Waitlist Entry", {"email": "not-an-address"}), 0)

	def test_free_text_is_clipped_to_the_column_width(self):
		waitlist.join(EMAIL, company="c" * 400, use_case="u" * 4000)

		entry = frappe.get_doc("Waitlist Entry", EMAIL)
		self.assertEqual(len(entry.company), waitlist.DATA_LIMIT)
		self.assertEqual(len(entry.use_case), waitlist.TEXT_LIMIT)

	def test_the_fourth_submission_in_an_hour_is_rate_limited(self):
		with _as_request(EMAIL):
			for _ in range(waitlist.JOINS_PER_HOUR):
				waitlist.join(EMAIL)
			with self.assertRaises(frappe.RateLimitExceededError):
				waitlist.join(EMAIL)

	def test_the_rate_limit_is_per_address(self):
		with _as_request(EMAIL):
			for _ in range(waitlist.JOINS_PER_HOUR):
				waitlist.join(EMAIL)
		with _as_request(OTHER_EMAIL):
			self.assertTrue(waitlist.join(OTHER_EMAIL)["joined"])

	def test_approval_creates_a_user_with_exactly_the_access_role(self):
		waitlist.join(EMAIL, full_name="Test Person")

		result = waitlist.approve([EMAIL])

		self.assertEqual(result["approved"], 1)
		user = frappe.get_doc("User", EMAIL)
		self.assertEqual([row.role for row in user.roles], [ACCESS_ROLE])
		entry = frappe.get_doc("Waitlist Entry", EMAIL)
		self.assertEqual(entry.status, "Approved")
		self.assertIsNotNone(entry.approved_on)

	def test_approving_twice_does_not_duplicate_the_role(self):
		waitlist.join(EMAIL)
		waitlist.approve([EMAIL])
		waitlist.approve([EMAIL])

		self.assertEqual([row.role for row in frappe.get_doc("User", EMAIL).roles], [ACCESS_ROLE])

	def test_approval_is_denied_to_a_non_admin(self):
		waitlist.join(EMAIL)
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			waitlist.approve([EMAIL])


class _as_request:
	"""Make the rate limiter apply — it is a no-op outside an HTTP request.

	The decorator keys on the request IP and the `email` form field, so a direct function call
	from a test would sail past it and the limit would never be exercised.
	"""

	def __init__(self, email):
		self.email = email

	def __enter__(self):
		frappe.cache.delete_keys("rl:")
		frappe.local.request = MagicMock(method="POST")
		frappe.local.request_ip = "127.0.0.1"
		frappe.local.form_dict = frappe._dict(cmd="benchpress.waitlist.join", email=self.email)
		return self

	def __exit__(self, *exception):
		frappe.cache.delete_keys("rl:")
		frappe.local.request = None
		frappe.local.form_dict = frappe._dict()
		return False
