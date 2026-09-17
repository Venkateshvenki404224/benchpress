# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""The operator alert: one escaped email per failure, and nothing while no address is set."""

import email
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import get_url_to_form

from benchpress import alerts
from benchpress.tests.fixtures import drop

ADDRESS = "alerts@example.com"
ERROR_LOG = "Error Log"
QUEUE = "Email Queue"
BENCH = SimpleNamespace(owner="tenant@example.com", name="bench-alert-test")


class TestOperatorAlert(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		previous = frappe.db.get_single_value(alerts.SETTINGS, "operator_alert_email")
		self.addCleanup(self._set_address, previous)
		self.addCleanup(self._drop_queued)

	def _set_address(self, value) -> None:
		frappe.db.set_single_value(alerts.SETTINGS, "operator_alert_email", value)
		frappe.db.commit()

	def _queued(self) -> list[str]:
		return frappe.get_all("Email Queue Recipient", filters={"recipient": ADDRESS}, pluck="parent")

	def _drop_queued(self) -> None:
		for name in self._queued():
			drop(QUEUE, name)

	def _html_of(self, queue_name: str) -> str:
		"""The HTML part as the recipient's client decodes it, past the quoted-printable wrapping."""
		parsed = email.message_from_string(frappe.db.get_value(QUEUE, queue_name, "message"))
		part = next(part for part in parsed.walk() if part.get_content_type() == "text/html")
		return part.get_payload(decode=True).decode()

	def test_nothing_is_queued_while_no_address_is_set(self):
		self._set_address(None)

		alerts.alert_operator("probe", "<b>x</b>")

		self.assertEqual(self._queued(), [])

	def test_one_email_is_queued_per_alert_once_an_address_is_set(self):
		self._set_address(ADDRESS)

		alerts.alert_operator("probe", "one")
		self.assertEqual(len(self._queued()), 1)

		alerts.alert_operator("probe", "two")
		self.assertEqual(len(self._queued()), 2)

	def test_markup_in_the_failure_text_arrives_escaped(self):
		self._set_address(ADDRESS)

		alerts.alert_operator("probe", "<script>alert(1)</script>")

		html = self._html_of(self._queued()[0])
		self.assertIn("&lt;script&gt;", html)
		self.assertNotIn("<script>", html)

	def test_a_long_failure_is_cut_and_keeps_its_owner_and_link(self):
		self._set_address(ADDRESS)
		reason = "a" * alerts.FAILURE_LIMIT + "PAST-THE-LIMIT"

		alerts.deploy_failed(BENCH, "CRM", reason)

		html = self._html_of(self._queued()[0])
		self.assertIn("a" * alerts.FAILURE_LIMIT, html)
		self.assertNotIn("PAST-THE-LIMIT", html)
		self.assertIn(BENCH.owner, html)
		self.assertIn(get_url_to_form("Bench Instance", BENCH.name), html)

	def test_a_failing_mailer_is_logged_and_never_raised(self):
		self._set_address(ADDRESS)
		subject = f"probe {frappe.generate_hash(length=8)}"
		title = f"BenchPress operator alert failed: {subject}"
		self.addCleanup(lambda: frappe.db.delete(ERROR_LOG, {"method": title}) or frappe.db.commit())

		with patch.object(frappe, "sendmail", side_effect=Exception("smtp is down")):
			alerts.alert_operator(subject, "text")

		self.assertEqual(frappe.db.count(ERROR_LOG, {"method": title}), 1)
