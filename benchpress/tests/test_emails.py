# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.model.base_document import get_controller
from frappe.tests import IntegrationTestCase
from frappe.utils import get_url

from benchpress import contact, emails
from benchpress.patches.refresh_approval_mail import DEAD_PROMISE
from benchpress.patches.refresh_approval_mail import execute as refresh_approval_mail
from benchpress.public_site.seed import relogo_email_templates
from benchpress.user import BenchPressPasswordResetMixin

REQUESTER = "emails-requester@example.com"
SENDER = "emails-sender@example.com"
ADMIN = "emails-admin@example.com"
ADMIN_ROLE = "BenchPress Admin"
ROLE_HOLDER = "emails-role-holder@example.com"
SET_PASSWORD_URL = "https://benchpress.example/update-password?key=abc123"
RESET_USER = "emails-reset@example.com"

# `_message()` files under "Sales"; routing it at the admin pins who the notice reaches.
ROUTED_TO_ADMIN = ({"label": "Sales", "route_to_email": ADMIN},)

# A row as the seed planted it before the logo existed, with a line of operator copy under it.
FAUX_LOGO_BODY = """<td style="padding:20px 28px;background-color:#0A1024;border-radius:13px 13px 0 0;">
	<table role="presentation" cellpadding="0" cellspacing="0" border="0">
		<tr>
			<td width="10" bgcolor="#4E8BFB" style="width:10px;height:10px;">&nbsp;</td>
			<td style="font-size:17px;color:#FFFFFF;">BENCHPRESS</td>
		</tr>
	</table>
</td>
<p>Hosted access is invite-only.</p>"""


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

	def test_the_operator_notice_names_the_requester_and_the_company(self):
		with patch.dict(frappe.conf, {contact.NOTIFY_KEY: ADMIN}):
			emails.notify_admins_of_access_request(_entry())

		self.assertEqual(self.sent["recipients"], [ADMIN])
		self.assertEqual(self.sent["subject"], "Access request from Priya Nair (Kettle Works)")
		self.assertIn("Two interns<br>starting on Monday", self.sent["message"])

	def test_the_approval_goes_to_the_requester_and_carries_the_way_in(self):
		emails.send_access_request_approved(_entry(), set_password_url=SET_PASSWORD_URL)

		self.assertEqual(self.sent["recipients"], [REQUESTER])
		self.assertEqual(self.sent["subject"], "Your BenchPress account is open")
		self.assertIn("Set your password", self.sent["message"])
		self.assertIn(SET_PASSWORD_URL, self.sent["message"])

	def test_the_approval_offers_the_sign_in_door_when_there_is_no_link(self):
		emails.send_access_request_approved(_entry())

		self.assertNotIn("Set your password", self.sent["message"])
		self.assertIn("Sign in", self.sent["message"])

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

	def test_the_acknowledgement_names_the_window_for_the_topic(self):
		default_window = contact.TOPICS[0]["window"]
		slower = next((row for row in contact.TOPICS if row["window"] != default_window), None)
		self.assertIsNotNone(slower, "no shipped topic differs from the first, so nothing is proven")

		emails.send_contact_received(_message(topic=slower["label"]))

		self.assertIn(slower["window"], self.sent["message"])
		self.assertNotIn(default_window, self.sent["message"])

	def test_the_contact_notice_is_subjected_by_topic_and_replies_to_the_sender(self):
		with patch.object(contact, "TOPICS", ROUTED_TO_ADMIN):
			emails.notify_admins_of_contact(_message())

		self.assertEqual(self.sent["recipients"], [ADMIN])
		self.assertEqual(self.sent["subject"], "[Sales] Ravi Kumar")
		self.assertEqual(self.sent["reply_to"], SENDER)

	def test_a_topic_routes_the_notice_to_its_own_address(self):
		routed = ({"label": "Sales", "route_to_email": "sales@benchpress.example"},)
		with patch.object(contact, "TOPICS", routed):
			emails.notify_admins_of_contact(_message())

		self.assertEqual(self.sent["recipients"], ["sales@benchpress.example"])

	def test_a_topic_with_no_address_falls_back_to_the_forwarding_address(self):
		with patch.dict(frappe.conf, {contact.NOTIFY_KEY: "hello@benchpress.example"}):
			emails.notify_admins_of_contact(_message())

		self.assertEqual(self.sent["recipients"], ["hello@benchpress.example"])

	def test_nothing_is_queued_when_there_is_nobody_to_tell(self):
		with patch.object(contact, "notify_email", return_value=""):
			emails.notify_admins_of_access_request(_entry())

		self.mailer.assert_not_called()

	def test_an_admin_role_holder_is_not_a_recipient(self):
		self._install_role_holder()

		with patch.dict(frappe.conf, {contact.NOTIFY_KEY: ADMIN}):
			emails.notify_admins_of_access_request(_entry())

		self.assertEqual(self.sent["recipients"], [ADMIN], "a role query is back in the recipient list")

	# the password reset mail

	def test_the_reset_mail_is_branded_and_signed_as_benchpress(self):
		emails.send_password_reset(self._reset_user(), SET_PASSWORD_URL)

		self.assertEqual(self.sent["recipients"], [RESET_USER])
		self.assertEqual(self.sent["subject"], "Reset your BenchPress password")
		self.assertIn(get_url(emails.LOGO_PATH), self.sent["message"])
		self.assertIn('alt="BenchPress"', self.sent["message"])
		self.assertIn("Thank you,<br>BenchPress", self.sent["message"])
		self.assertIn(SET_PASSWORD_URL, self.sent["message"])
		self.assertNotIn("Administrator", self.sent["message"])

	def test_the_reset_mail_is_sent_at_once_and_redacted_after(self):
		emails.send_password_reset(self._reset_user(), SET_PASSWORD_URL)

		self.assertTrue(self.sent["now"], "a queued reset mail waits on the scheduler")
		self.assertTrue(self.sent["redact_message_after_send"], "the key would stay in Email Queue")

	def test_the_framework_reaches_the_branded_mail(self):
		user = self._reset_user()

		user._reset_password(send_email=True)

		self.assertIn(RESET_USER, self.sent["recipients"])
		self.assertEqual(self.sent["subject"], "Reset your BenchPress password")

	def test_the_user_class_carries_the_mixin(self):
		self.assertTrue(issubclass(get_controller("User"), BenchPressPasswordResetMixin))

	# email templates

	def test_a_deleted_template_row_falls_back_to_the_shipped_body(self):
		with patch.object(frappe.db, "exists", return_value=False):
			emails.send_access_request_received(_entry())

		self.assertEqual(self.sent["subject"], "Your BenchPress access request — REQ-A1B2-C3D4")
		self.assertIn(emails.LOGO_PATH, self.sent["message"], "the shipped body did not render")
		self.assertNotIn("{{", self.sent["message"], "an interpolation was left unrendered")

	def test_every_shipped_body_carries_the_logo_over_an_absolute_url(self):
		"""A mail client resolves nothing relative, so the header src must arrive absolute."""
		patch.dict(frappe.conf, {contact.NOTIFY_KEY: ADMIN}).start()
		patch.object(contact, "TOPICS", ROUTED_TO_ADMIN).start()

		with patch.object(frappe.db, "exists", return_value=False):
			for send, row in self._every_send():
				self.mailer.reset_mock()
				send(row)
				with self.subTest(send=send.__name__):
					self.assertIn(f'src="{get_url(emails.LOGO_PATH)}?v=', self.sent["message"])
					self.assertIn('alt="BenchPress"', self.sent["message"])

	def test_an_operator_edit_in_desk_wins_over_the_shipped_body(self):
		self._install_template(
			emails.ACCESS_APPROVED,
			subject="Welcome aboard, {{ full_name }}",
			body="<p>{{ reference }}</p>",
		)

		emails.send_access_request_approved(_entry())

		self.assertEqual(self.sent["subject"], "Welcome aboard, Priya Nair")
		self.assertEqual(self.sent["message"], "<p>REQ-A1B2-C3D4</p>")

	def test_a_row_that_still_promises_a_welcome_mail_is_re_seeded(self):
		self._install_template(
			emails.ACCESS_APPROVED, subject="x", body=f"<p>the link in the {DEAD_PROMISE}</p>"
		)

		refresh_approval_mail()

		body = frappe.db.get_value("Email Template", emails.ACCESS_APPROVED, "response_html")
		self.assertNotIn(DEAD_PROMISE, body)
		self.assertIn("Set your password", body)

	def test_a_row_that_no_longer_promises_one_is_left_alone(self):
		self._install_template(emails.ACCESS_APPROVED, subject="x", body="<p>operator copy</p>")

		refresh_approval_mail()

		self.assertEqual(
			frappe.db.get_value("Email Template", emails.ACCESS_APPROVED, "response_html"),
			"<p>operator copy</p>",
		)

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

	def test_a_row_seeded_before_the_logo_is_re_branded_in_place(self):
		self._install_template(emails.ACCESS_APPROVED, subject="x", body=FAUX_LOGO_BODY)

		relogo_email_templates()

		body = frappe.db.get_value("Email Template", emails.ACCESS_APPROVED, "response_html")
		self.assertNotIn("BENCHPRESS", body)
		self.assertIn('alt="BenchPress"', body)
		self.assertIn("<p>Hosted access is invite-only.</p>", body, "the operator's copy was lost")

	def test_re_branding_a_row_that_already_carries_the_logo_changes_nothing(self):
		self._install_template(emails.ACCESS_APPROVED, subject="x", body=FAUX_LOGO_BODY)
		relogo_email_templates()
		once = frappe.db.get_value("Email Template", emails.ACCESS_APPROVED, "response_html")

		relogo_email_templates()

		twice = frappe.db.get_value("Email Template", emails.ACCESS_APPROVED, "response_html")
		self.assertEqual(once, twice)

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
		with patch.object(contact, "TOPICS", ROUTED_TO_ADMIN):
			emails.notify_admins_of_contact(_message(message="<script>alert(1)</script>"))

		self.assertNotIn("<script>", self.sent["message"])
		self.assertIn("&lt;script&gt;", self.sent["message"])

	def test_a_double_escaping_operator_edit_still_reads_as_text(self):
		self._install_template(emails.CONTACT_FILED, subject="x", body="<p>{{ message | e }}</p>")

		with patch.object(contact, "TOPICS", ROUTED_TO_ADMIN):
			emails.notify_admins_of_contact(_message(message="Ampersand & co"))

		self.assertEqual(self.sent["message"], "<p>Ampersand &amp; co</p>")

	# helpers

	def _reset_user(self):
		self.addCleanup(self._drop_reset_user)
		self._drop_reset_user()
		return frappe.get_doc(
			{
				"doctype": "User",
				"email": RESET_USER,
				"first_name": "Reset",
				"last_name": "Person",
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)

	def _drop_reset_user(self) -> None:
		if frappe.db.exists("User", RESET_USER):
			frappe.delete_doc("User", RESET_USER, force=True, ignore_permissions=True)

	def _every_send(self) -> tuple:
		"""One call per shipped body: the four that reach a person and the two that reach the admins."""
		entry, message = _entry(), _message()
		return (
			(emails.send_access_request_received, entry),
			(emails.notify_admins_of_access_request, entry),
			(emails.send_access_request_approved, entry),
			(emails.send_access_request_rejected, entry),
			(emails.send_contact_received, message),
			(emails.notify_admins_of_contact, message),
		)

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

	def _install_role_holder(self) -> None:
		self.addCleanup(self._drop_role_holder)
		self._drop_role_holder()
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": ROLE_HOLDER,
				"first_name": "Emails",
				"last_name": "Admin",
				"user_type": "System User",
				"send_welcome_email": 0,
			}
		)
		user.append("roles", {"role": ADMIN_ROLE})
		user.insert(ignore_permissions=True)

	def _drop_role_holder(self) -> None:
		if frappe.db.exists("User", ROLE_HOLDER):
			frappe.delete_doc("User", ROLE_HOLDER, force=True, ignore_permissions=True)
