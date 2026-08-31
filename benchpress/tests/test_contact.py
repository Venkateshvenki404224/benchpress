# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

import benchpress
from benchpress import contact
from benchpress.benchpress.doctype.contact_message.contact_message import (
	MESSAGE_LIMIT,
	NAME_LIMIT,
	TOPIC_LIMIT,
)
from benchpress.tests.guest_request import as_request

EMAIL = "contact-test@example.com"
OTHER_EMAIL = "contact-other@example.com"
TOPICS = ("Hosted access", "Setup or migration", "Bug or issue")
SUCCESS_BODY = "Sent. A person reads this, not a queue."


def _delete_messages(*emails):
	for name in frappe.get_all("Contact Message", filters={"email": ("in", emails)}, pluck="name"):
		frappe.delete_doc("Contact Message", name, force=True, ignore_permissions=True)


class TestContact(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.settings = self.use_settings()
		self.emails = self.use_mailer()
		_delete_messages(EMAIL, OTHER_EMAIL)
		frappe.cache.delete_keys("rl:")
		self.addCleanup(frappe.cache.delete_keys, "rl:")
		self.addCleanup(_delete_messages, EMAIL, OTHER_EMAIL)
		self.addCleanup(frappe.set_user, "Administrator")

	def use_settings(self, **overrides):
		settings = frappe.get_doc(
			{
				"doctype": contact.SETTINGS,
				"title": "Talk to us.",
				"form_success_body": SUCCESS_BODY,
				"acknowledge_sender": 1,
				"notify_email": "hello@benchpress.dev",
				"topics": [
					{"label": label, "is_default": int(index == 0)} for index, label in enumerate(TOPICS)
				],
				"response_times": [
					{"subject": TOPICS[0], "window": "1 business day"},
					{"subject": "GitHub issues", "window": "2-3 days"},
				],
				**overrides,
			}
		)
		self.patch(patch.object(contact, "page_settings", return_value=settings))
		return settings

	def use_mailer(self, **behaviour):
		mailer = MagicMock(**behaviour)
		self.patch(patch.object(benchpress, "emails", mailer, create=True))
		return mailer

	def patch(self, patcher):
		patcher.start()
		self.addCleanup(patcher.stop)

	def test_a_valid_submission_stores_one_new_row(self):
		response = contact.submit("Ravi Kumar", EMAIL, "We run ERPNext for 40 people.", TOPICS[1])

		self.assertTrue(response["sent"])
		self.assertEqual(response["message"], SUCCESS_BODY)
		message = frappe.get_doc("Contact Message", {"email": EMAIL})
		self.assertEqual(message.sender_name, "Ravi Kumar")
		self.assertEqual(message.topic, TOPICS[1])
		self.assertEqual(message.status, "New")
		self.assertIsNone(message.answered_on)

	def test_the_success_text_comes_from_desk_and_falls_back_to_the_seed(self):
		self.use_settings(form_success_body=None)

		self.assertEqual(contact.submit("Ravi", EMAIL, "hello")["message"], contact.SUCCESS_BODY)

	def test_a_topic_the_page_never_offered_becomes_the_default_chip(self):
		contact.submit("Ravi", EMAIL, "hello", "<script>alert(1)</script>")

		self.assertEqual(frappe.db.get_value("Contact Message", {"email": EMAIL}, "topic"), TOPICS[0])

	def test_a_second_message_from_the_same_address_gets_its_own_row(self):
		contact.submit("Ravi", EMAIL, "first")
		contact.submit("Ravi", EMAIL, "second")

		self.assertEqual(frappe.db.count("Contact Message", {"email": EMAIL}), 2)

	def test_an_invalid_address_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			contact.submit("Ravi", "not-an-address", "hello")
		self.assertEqual(frappe.db.count("Contact Message", {"sender_name": "Ravi"}), 0)

	def test_an_empty_message_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			contact.submit("Ravi", EMAIL, "   ")
		self.assertEqual(frappe.db.count("Contact Message", {"email": EMAIL}), 0)

	def test_a_missing_name_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			contact.submit("", EMAIL, "hello")
		self.assertEqual(frappe.db.count("Contact Message", {"email": EMAIL}), 0)

	def test_free_text_is_clipped_to_the_column_width(self):
		long_topic = "t" * 200
		self.use_settings(topics=[{"label": long_topic, "is_default": 1}])

		contact.submit("n" * 400, EMAIL, "m" * 6000, long_topic)

		message = frappe.get_doc("Contact Message", {"email": EMAIL})
		self.assertEqual(len(message.sender_name), NAME_LIMIT)
		self.assertEqual(len(message.message), MESSAGE_LIMIT)
		self.assertEqual(len(message.topic), TOPIC_LIMIT)

	def test_the_fourth_message_in_an_hour_is_rate_limited(self):
		with as_request():
			for _ in range(contact.MESSAGES_PER_HOUR):
				contact.submit("Ravi", EMAIL, "hello")
			with self.assertRaises(frappe.RateLimitExceededError):
				contact.submit("Ravi", EMAIL, "hello")

	def test_the_rate_limit_is_per_email(self):
		with as_request():
			for _ in range(contact.MESSAGES_PER_HOUR):
				contact.submit("Ravi", EMAIL, "hello")

			self.assertTrue(contact.submit("Priya", OTHER_EMAIL, "hello")["sent"])

	def test_both_notifications_fire_on_a_send(self):
		contact.submit("Ravi", EMAIL, "hello")

		self.assertEqual(self.emails.send_contact_received.call_count, 1)
		self.assertEqual(self.emails.notify_admins_of_contact.call_count, 1)
		sent = self.emails.notify_admins_of_contact.call_args.args[0]
		self.assertEqual(sent.email, EMAIL)

	def test_the_acknowledgement_is_skipped_when_desk_switches_it_off(self):
		self.use_settings(acknowledge_sender=0)

		contact.submit("Ravi", EMAIL, "hello")

		self.emails.send_contact_received.assert_not_called()
		self.emails.notify_admins_of_contact.assert_called_once()

	def test_a_failing_mailer_does_not_lose_the_message(self):
		self.emails = self.use_mailer(send_contact_received=MagicMock(side_effect=Exception("no smtp")))

		self.assertTrue(contact.submit("Ravi", EMAIL, "hello")["sent"])

		self.assertEqual(frappe.db.count("Contact Message", {"email": EMAIL}), 1)
		self.emails.notify_admins_of_contact.assert_called_once()

	def test_a_guest_cannot_read_the_messages_back(self):
		contact.submit("Ravi", EMAIL, "hello")

		frappe.set_user("Guest")

		self.assertFalse(frappe.has_permission("Contact Message", "read"))
		with self.assertRaises(frappe.PermissionError):
			frappe.get_list("Contact Message")

	def test_mark_answered_stamps_who_and_when(self):
		contact.submit("Ravi", EMAIL, "hello")
		name = frappe.db.get_value("Contact Message", {"email": EMAIL})

		self.assertEqual(contact.mark_answered([name])["answered"], 1)

		message = frappe.get_doc("Contact Message", name)
		self.assertEqual(message.status, "Answered")
		self.assertEqual(message.answered_by, "Administrator")
		self.assertIsNotNone(message.answered_on)

	def test_mark_answered_is_denied_to_a_non_admin(self):
		contact.submit("Ravi", EMAIL, "hello")
		name = frappe.db.get_value("Contact Message", {"email": EMAIL})
		frappe.set_user("Guest")

		with self.assertRaises(frappe.PermissionError):
			contact.mark_answered([name])
		self.assertEqual(frappe.db.get_value("Contact Message", name, "status"), "New")


class TestContactPageSettings(IntegrationTestCase):
	def settings(self, **overrides):
		return frappe.get_doc({"doctype": contact.SETTINGS, "title": "Talk to us.", **overrides})

	def test_two_default_topics_are_refused(self):
		settings = self.settings(
			topics=[{"label": "One", "is_default": 1}, {"label": "Two", "is_default": 1}]
		)

		with self.assertRaises(frappe.ValidationError):
			settings.validate()

	def test_the_first_topic_is_the_default_when_none_is_flagged(self):
		settings = self.settings(topics=[{"label": "One"}, {"label": "Two"}])

		self.assertEqual(settings.default_topic(), "One")
		self.assertEqual(settings.resolve_topic("Two"), "Two")
		self.assertEqual(settings.resolve_topic("Three"), "One")

	def test_a_page_with_no_topics_stores_no_topic(self):
		self.assertEqual(self.settings().resolve_topic("Hosted access"), "")

	def test_a_topic_routes_to_its_own_address_before_the_page_default(self):
		settings = self.settings(
			notify_email="hello@benchpress.dev",
			topics=[{"label": "Bug", "route_to_email": "bugs@benchpress.dev"}, {"label": "Sales"}],
		)

		self.assertEqual(settings.route_for("Bug"), "bugs@benchpress.dev")
		self.assertEqual(settings.route_for("Sales"), "hello@benchpress.dev")

	def test_the_response_window_falls_back_to_the_first_row(self):
		settings = self.settings(
			response_times=[
				{"subject": "Sales", "window": "1 business day"},
				{"subject": "Bug", "window": "3 days"},
			]
		)

		self.assertEqual(settings.response_window("Bug"), "3 days")
		self.assertEqual(settings.response_window("Anything else"), "1 business day")
