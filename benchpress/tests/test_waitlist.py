# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import re
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from benchpress import waitlist
from benchpress.benchpress.doctype.waitlist_entry.waitlist_entry import (
	ACCESS_ROLE,
	WEBSITE_USER,
	derive_reference,
)
from benchpress.tests.guest_request import as_request

EMAIL = "waitlist-test@example.com"
OTHER_EMAIL = "waitlist-other@example.com"
REFERENCE_FORMAT = re.compile(r"^REQ-[0-9A-F]{4}-[0-9A-F]{4}$")

JOIN_SENDER = "benchpress.waitlist.send_notice"
DECISION_SENDER = "benchpress.benchpress.doctype.waitlist_entry.waitlist_entry.send_notice"


def _app_roles(user_doc) -> list[str]:
	# Only the roles this app grants. Another installed app appending its own is not a failure
	# here — the wiki app gives every new user `Wiki User`.
	return [row.role for row in user_doc.roles if row.role.startswith("BenchPress")]


def _delete_entry(email):
	if frappe.db.exists("Waitlist Entry", email):
		frappe.delete_doc("Waitlist Entry", email, force=True, ignore_permissions=True)
	if frappe.db.exists("User", email):
		frappe.delete_doc("User", email, force=True, ignore_permissions=True)


class TestWaitlist(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self._silence_outgoing_mail()
		frappe.cache.delete_keys("rl:")
		self.addCleanup(frappe.cache.delete_keys, "rl:")
		for email in (EMAIL, OTHER_EMAIL):
			_delete_entry(email)
			self.addCleanup(_delete_entry, email)
		self.addCleanup(frappe.set_user, "Administrator")

	def _silence_outgoing_mail(self) -> None:
		# `None`, not a mock: `User.send_welcome_mail_to_user` reads `.message` off the return value.
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
		waitlist.join(EMAIL, company="c" * 400, use_case="u" * 4000, expected_apps="a" * 400)

		entry = frappe.get_doc("Waitlist Entry", EMAIL)
		self.assertEqual(len(entry.company), waitlist.DATA_LIMIT)
		self.assertEqual(len(entry.use_case), waitlist.TEXT_LIMIT)
		self.assertEqual(len(entry.expected_apps), waitlist.DATA_LIMIT)

	def test_the_signup_form_fields_are_recorded(self):
		waitlist.join(
			EMAIL,
			full_name="Test Person",
			team_size="16 or more",
			intent="Agent / automation",
			expected_apps="ERPNext v15, two custom apps",
			consented="1",
			source="Landing Waitlist",
		)

		entry = frappe.get_doc("Waitlist Entry", EMAIL)
		self.assertEqual(entry.team_size, "16 or more")
		self.assertEqual(entry.intent, "Agent / automation")
		self.assertEqual(entry.expected_apps, "ERPNext v15, two custom apps")
		self.assertEqual(entry.consented, 1)
		self.assertEqual(entry.source, "Landing Waitlist")

	def test_a_select_value_the_column_does_not_offer_becomes_the_default(self):
		waitlist.join(EMAIL, team_size="900", intent="'; drop table", source="Desk\nApproved")

		entry = frappe.get_doc("Waitlist Entry", EMAIL)
		self.assertEqual(entry.team_size, "1 — just me")
		self.assertEqual(entry.intent, "Hosted account")
		self.assertEqual(entry.source, "Signup Page")

	def test_consented_is_recorded_and_never_enforced(self):
		self.assertTrue(waitlist.join(EMAIL)["joined"])
		self.assertEqual(frappe.db.get_value("Waitlist Entry", EMAIL, "consented"), 0)

	def test_an_argument_outside_the_signature_is_not_accepted(self):
		with self.assertRaises(TypeError):
			waitlist.join(EMAIL, status="Approved")

	def test_the_reference_is_formatted_and_derived_from_the_address_alone(self):
		first = waitlist.join(EMAIL)["reference"]

		self.assertRegex(first, REFERENCE_FORMAT)
		self.assertEqual(first, derive_reference(EMAIL.upper()), "case must not change the handle")
		self.assertEqual(first, frappe.get_doc("Waitlist Entry", EMAIL).request_reference())
		self.assertNotEqual(first, derive_reference(OTHER_EMAIL))

	def test_the_reference_is_the_same_before_and_after_the_row_exists(self):
		before = derive_reference(EMAIL)
		self.assertEqual(waitlist.join(EMAIL)["reference"], before)
		self.assertEqual(waitlist.join(EMAIL)["reference"], before)

	def test_a_duplicate_join_mails_nobody_a_second_time(self):
		with patch(JOIN_SENDER) as sender:
			waitlist.join(EMAIL)
			self.assertEqual(
				[call.args[0] for call in sender.call_args_list],
				["send_access_request_received", "notify_admins_of_access_request"],
			)
			sender.reset_mock()

			waitlist.join(EMAIL)
			sender.assert_not_called()

	def test_the_fourth_submission_in_an_hour_is_rate_limited(self):
		with as_request():
			for _ in range(waitlist.JOINS_PER_HOUR):
				waitlist.join(EMAIL)
			with self.assertRaises(frappe.RateLimitExceededError):
				waitlist.join(EMAIL)

	def test_the_rate_limit_is_per_email(self):
		with as_request():
			for _ in range(waitlist.JOINS_PER_HOUR):
				waitlist.join(EMAIL)

			self.assertTrue(waitlist.join(OTHER_EMAIL)["joined"])

	def test_approval_creates_a_user_with_exactly_the_access_role(self):
		waitlist.join(EMAIL, full_name="Test Person")

		result = waitlist.approve([EMAIL])

		self.assertEqual(result["approved"], 1)
		user = frappe.get_doc("User", EMAIL)
		self.assertEqual(_app_roles(user), [ACCESS_ROLE])
		entry = frappe.get_doc("Waitlist Entry", EMAIL)
		self.assertEqual(entry.status, "Approved")
		self.assertIsNotNone(entry.approved_on)

	def test_approval_creates_a_website_user(self):
		waitlist.join(EMAIL, full_name="Test Person")

		waitlist.approve([EMAIL])

		self.assertEqual(frappe.db.get_value("User", EMAIL, "user_type"), WEBSITE_USER)

	def test_the_new_user_stays_a_website_user_when_the_role_grants_desk_access(self):
		self._grant_the_access_role_desk_access()
		waitlist.join(EMAIL, full_name="Test Person")

		waitlist.approve([EMAIL])
		waitlist.approve([EMAIL])

		self.assertEqual(frappe.db.get_value("User", EMAIL, "user_type"), WEBSITE_USER)

	def _grant_the_access_role_desk_access(self) -> None:
		was = frappe.db.get_value("Role", ACCESS_ROLE, "desk_access")
		self.addCleanup(frappe.db.set_value, "Role", ACCESS_ROLE, "desk_access", was)
		frappe.db.set_value("Role", ACCESS_ROLE, "desk_access", 1)

	def test_approving_twice_does_not_duplicate_the_role(self):
		waitlist.join(EMAIL)
		waitlist.approve([EMAIL])
		waitlist.approve([EMAIL])

		self.assertEqual(_app_roles(frappe.get_doc("User", EMAIL)), [ACCESS_ROLE])

	def test_approval_is_denied_to_a_non_admin(self):
		waitlist.join(EMAIL)
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			waitlist.approve([EMAIL])

	def test_approval_mails_a_set_password_link_for_an_account_it_created(self):
		waitlist.join(EMAIL)

		with patch(DECISION_SENDER) as sender:
			waitlist.approve([EMAIL])

		self.assertIn("/update-password?key=", sender.call_args.kwargs["set_password_url"])

	def test_an_address_that_already_has_a_login_is_mailed_no_link(self):
		frappe.get_doc(
			{"doctype": "User", "email": EMAIL, "first_name": "Already", "send_welcome_email": 0}
		).insert(ignore_permissions=True)
		waitlist.join(EMAIL)

		with patch(DECISION_SENDER) as sender:
			waitlist.approve([EMAIL])

		self.assertEqual(sender.call_args.kwargs["set_password_url"], "")

	def test_frappes_own_welcome_mail_is_not_asked_for(self):
		waitlist.join(EMAIL)

		waitlist.approve([EMAIL])

		self.assertEqual(frappe.db.get_value("User", EMAIL, "send_welcome_email"), 0)

	def test_the_approval_notice_follows_the_decision_not_the_call(self):
		waitlist.join(EMAIL)
		with patch(DECISION_SENDER) as sender:
			waitlist.approve([EMAIL])
			waitlist.approve([EMAIL])

		self.assertEqual([call.args[0] for call in sender.call_args_list], ["send_access_request_approved"])

	def test_rejection_records_the_decision_and_clips_the_reason(self):
		waitlist.join(EMAIL)

		self.assertEqual(waitlist.reject([EMAIL], reason="r" * 4000)["rejected"], 1)

		entry = frappe.get_doc("Waitlist Entry", EMAIL)
		self.assertEqual(entry.status, "Rejected")
		self.assertEqual(len(entry.rejection_reason), waitlist.TEXT_LIMIT)
		self.assertIsNotNone(entry.rejected_on)
		self.assertIsNone(entry.approved_on)

	def test_approving_a_rejected_entry_clears_the_rejection_stamp(self):
		waitlist.join(EMAIL)
		waitlist.reject([EMAIL], reason="no capacity")

		waitlist.approve([EMAIL])

		entry = frappe.get_doc("Waitlist Entry", EMAIL)
		self.assertIsNone(entry.rejected_on)
		self.assertIsNotNone(entry.approved_on)

	def test_rejection_is_denied_to_a_non_admin(self):
		waitlist.join(EMAIL)
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			waitlist.reject([EMAIL])
