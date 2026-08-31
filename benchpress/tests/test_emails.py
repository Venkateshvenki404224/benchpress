# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from benchpress import emails

REQUESTER = "emails-requester@example.com"
SENDER = "emails-sender@example.com"
ADMIN = "emails-admin@example.com"
ADMIN_ROLE = "BenchPress Admin"


def _entry(**overrides) -> frappe._dict:
	row = frappe._dict(
		{
			"doctype": "Waitlist Entry",
			"name": REQUESTER,
			"full_name": "Priya Nair",
			"company": "Kettle Works",
			"team_size": "16 or more",
			"intent": "Hosted account",
			"expected_apps": "erpnext, hrms",
			"use_case": "Two interns\nstarting on Monday",
			"creation": "2026-08-30 09:15:00",
			"rejection_reason": "",
		}
	)
	row.update(overrides)
	row.request_reference = lambda: "REQ-A1B2-C3D4"
	return row


def _message(**overrides) -> frappe._dict:
	row = frappe._dict(
		{
			"doctype": "Contact Message",
			"name": "b7f3c1d9e2",
			"sender_name": "Ravi Kumar",
			"email": SENDER,
			"topic": "Sales",
			"message": "Quote for setup?",
			"creation": "2026-08-30 09:15:00",
		}
	)
	row.update(overrides)
	return row


class TestEmails(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")
		self.mailer = patch("frappe.sendmail").start()
		self.addCleanup(patch.stopall)

	@property
	def sent(self) -> dict:
		"""The keyword arguments of the one queued email."""
		self.assertEqual(self.mailer.call_count, 1, "expected exactly one email")
		return self.mailer.call_args.kwargs

	def test_a_site_with_no_outgoing_account_still_completes_the_operation(self):
		"""CI has no Email Account, and `frappe.in_test` forces the queue to send at once."""
		self.mailer.side_effect = frappe.OutgoingEmailError("Email Account not setup")

		with patch.object(frappe, "log_error") as logged:
			emails.send_access_request_received(_entry())

		self.assertEqual(self.mailer.call_count, 1)
		self.assertTrue(logged.called, "the failure must be logged, not swallowed silently")

	# recipients and subjects

	def test_the_requester_gets_the_acknowledgement(self):
		emails.send_access_request_received(_entry())

		self.assertEqual(self.sent["recipients"], [REQUESTER])
		self.assertEqual(self.sent["subject"], "Your BenchPress access request — REQ-A1B2-C3D4")
		self.assertIn("REQ-A1B2-C3D4", self.sent["message"])

	def test_the_admin_notice_names_the_requester_and_the_company(self):
		with patch.object(emails, "admin_recipients", return_value=[ADMIN]):
			emails.notify_admins_of_access_request(_entry())

		self.assertEqual(self.sent["recipients"], [ADMIN])
		self.assertEqual(self.sent["subject"], "Access request from Priya Nair (Kettle Works)")
		self.assertIn("Two interns<br>starting on Monday", self.sent["message"])

	def test_the_approval_goes_to_the_requester_and_carries_no_password(self):
		emails.send_access_request_approved(_entry())

		self.assertEqual(self.sent["recipients"], [REQUESTER])
		self.assertEqual(self.sent["subject"], "Your BenchPress account is open")
		self.assertIn("separate welcome email", self.sent["message"])

	def test_the_decline_carries_the_reason_and_the_self_hosting_door(self):
		emails.send_access_request_rejected(_entry(rejection_reason="Hosted access is invite-only."))

		self.assertEqual(self.sent["recipients"], [REQUESTER])
		self.assertEqual(self.sent["subject"], "About your BenchPress access request")
		self.assertIn("Hosted access is invite-only.", self.sent["message"])
		self.assertIn(emails.REPO_URL, self.sent["message"])

	def test_the_contact_sender_gets_an_acknowledgement(self):
		emails.send_contact_received(_message())

		self.assertEqual(self.sent["recipients"], [SENDER])
		self.assertEqual(self.sent["subject"], "We got your message")

	def test_the_contact_notice_is_subjected_by_topic_and_replies_to_the_sender(self):
		with patch.object(emails, "_contact_notice_recipients", return_value=[ADMIN]):
			emails.notify_admins_of_contact(_message())

		self.assertEqual(self.sent["recipients"], [ADMIN])
		self.assertEqual(self.sent["subject"], "[Sales] Ravi Kumar")
		self.assertEqual(self.sent["reply_to"], SENDER)

	def test_an_operator_can_switch_the_acknowledgement_off(self):
		settings = frappe._dict({"acknowledge_sender": 0})
		with patch.object(emails, "_contact_settings", return_value=settings):
			emails.send_contact_received(_message())

		self.mailer.assert_not_called()

	def test_a_site_that_never_saved_the_single_still_acknowledges(self):
		with patch.object(emails, "_contact_settings", return_value=None):
			emails.send_contact_received(_message())

		self.assertEqual(self.sent["recipients"], [SENDER])

	def test_a_topic_routes_the_notice_to_its_own_address(self):
		settings = frappe._dict(
			{
				"notify_email": "hello@benchpress.example",
				"topics": [frappe._dict({"label": "Sales", "route_to_email": "sales@benchpress.example"})],
			}
		)
		with patch.object(emails, "_contact_settings", return_value=settings):
			emails.notify_admins_of_contact(_message())

		self.assertEqual(self.sent["recipients"], ["sales@benchpress.example"])

	def test_a_topic_with_no_address_falls_back_to_the_notify_address(self):
		settings = frappe._dict({"notify_email": "hello@benchpress.example", "topics": []})
		with patch.object(emails, "_contact_settings", return_value=settings):
			emails.notify_admins_of_contact(_message())

		self.assertEqual(self.sent["recipients"], ["hello@benchpress.example"])

	def test_nothing_is_queued_when_there_is_nobody_to_tell(self):
		with patch.object(emails, "admin_recipients", return_value=[]):
			emails.notify_admins_of_access_request(_entry())

		self.mailer.assert_not_called()

	# email templates

	def test_a_deleted_template_row_falls_back_to_the_shipped_body(self):
		with patch.object(frappe.db, "exists", return_value=False):
			emails.send_access_request_received(_entry())

		self.assertEqual(self.sent["subject"], "Your BenchPress access request — REQ-A1B2-C3D4")
		self.assertIn("BENCH", self.sent["message"], "the shipped body did not render")
		self.assertNotIn("{{", self.sent["message"], "an interpolation was left unrendered")

	def test_an_operator_edit_in_desk_wins_over_the_shipped_body(self):
		self._install_template(
			emails.ACCESS_APPROVED,
			subject="Welcome aboard, {{ full_name }}",
			body="<p>{{ reference }}</p>",
		)

		emails.send_access_request_approved(_entry())

		self.assertEqual(self.sent["subject"], "Welcome aboard, Priya Nair")
		self.assertEqual(self.sent["message"], "<p>REQ-A1B2-C3D4</p>")

	def test_every_shipped_body_renders_from_an_empty_document(self):
		bare = frappe._dict({"name": REQUESTER, "email": SENDER, "sender_name": ""})
		with patch.object(frappe.db, "exists", return_value=False):
			for send in (
				emails.send_access_request_received,
				emails.send_access_request_approved,
				emails.send_access_request_rejected,
				emails.send_contact_received,
			):
				self.mailer.reset_mock()
				send(bare)
				self.assertTrue(self.sent["message"].strip())

	# failure containment

	def test_a_send_failure_does_not_reach_the_caller(self):
		self.mailer.side_effect = Exception("no outgoing email account")

		with patch.object(frappe, "log_error") as logged:
			emails.send_access_request_received(_entry())

		logged.assert_called_once()

	def test_a_broken_context_does_not_reach_the_caller(self):
		with patch.object(emails, "_request_context", side_effect=Exception("bad row")):
			with patch.object(frappe, "log_error") as logged:
				emails.send_access_request_approved(_entry())

		self.mailer.assert_not_called()
		logged.assert_called_once()

	# escaping

	def test_guest_text_is_escaped_before_it_reaches_the_body(self):
		with patch.object(emails, "_contact_notice_recipients", return_value=[ADMIN]):
			emails.notify_admins_of_contact(_message(message="<script>alert(1)</script>"))

		self.assertNotIn("<script>", self.sent["message"])
		self.assertIn("&lt;script&gt;", self.sent["message"])

	def test_a_double_escaping_operator_edit_still_reads_as_text(self):
		self._install_template(emails.CONTACT_FILED, subject="x", body="<p>{{ message | e }}</p>")

		with patch.object(emails, "_contact_notice_recipients", return_value=[ADMIN]):
			emails.notify_admins_of_contact(_message(message="Ampersand & co"))

		self.assertEqual(self.sent["message"], "<p>Ampersand &amp; co</p>")

	# admin recipients

	def test_admin_recipients_are_the_enabled_role_holders(self):
		self._install_admin_user()

		self.assertIn(ADMIN, emails.admin_recipients())

	def test_a_disabled_admin_is_not_a_recipient(self):
		self._install_admin_user(enabled=0)

		self.assertNotIn(ADMIN, emails.admin_recipients())

	# helpers

	def _install_template(self, name: str, subject: str, body: str) -> None:
		if frappe.db.exists("Email Template", name):
			previous = frappe.get_doc("Email Template", name).as_dict()
			frappe.delete_doc("Email Template", name, force=True, ignore_permissions=True)
			self.addCleanup(self._restore_template, previous)
		else:
			self.addCleanup(self._drop_template, name)
		frappe.get_doc(
			{
				"doctype": "Email Template",
				"name": name,
				"subject": subject,
				"use_html": 1,
				"response_html": body,
			}
		).insert(ignore_permissions=True)
		frappe.clear_cache(doctype="Email Template")

	def _restore_template(self, previous: dict) -> None:
		self._drop_template(previous["name"])
		frappe.get_doc(previous).insert(ignore_permissions=True, set_name=previous["name"])
		frappe.clear_cache(doctype="Email Template")

	def _drop_template(self, name: str) -> None:
		if frappe.db.exists("Email Template", name):
			frappe.delete_doc("Email Template", name, force=True, ignore_permissions=True)
		frappe.clear_cache(doctype="Email Template")

	def _install_admin_user(self, enabled: int = 1) -> None:
		self.addCleanup(self._drop_admin_user)
		self._drop_admin_user()
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": ADMIN,
				"first_name": "Emails",
				"last_name": "Admin",
				"user_type": "System User",
				"enabled": enabled,
				"send_welcome_email": 0,
			}
		)
		user.append("roles", {"role": ADMIN_ROLE})
		user.insert(ignore_permissions=True)

	def _drop_admin_user(self) -> None:
		if frappe.db.exists("User", ADMIN):
			frappe.delete_doc("User", ADMIN, force=True, ignore_permissions=True)
