# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""Each public form counts on its own, and one address cannot buy more by changing its email."""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.website.serve import get_response_content

import benchpress
from benchpress import contact, signup, throttle, waitlist
from benchpress.credits import config
from benchpress.tests.guest_request import as_request

OTHER_ADDRESS = "198.51.100.8"
EMAIL_PATTERN = "limits-%@example.com"
TOO_MANY = "You hit the rate limit"

CONTACT_ROUTE = "/contact"
SIGNUP_ROUTE = "/signup"


def email(tag) -> str:
	return f"limits-{tag}@example.com"


def _clear_rows():
	for doctype in ("Contact Message", "Waitlist Entry"):
		for name in frappe.get_all(doctype, filters={"email": ("like", EMAIL_PATTERN)}, pluck="name"):
			frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)


class TestPublicFormLimits(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.use(patch.object(benchpress, "emails", MagicMock(), create=True))
		self.use(patch.object(waitlist, "send_notice", MagicMock()))
		self.use(patch.object(signup, "frappe_sign_up", MagicMock(return_value=(1, "ok"))))
		self.use(patch.object(config, "credits_enabled", return_value=False))
		self.use(patch("frappe.sendmail", return_value=None))
		_clear_rows()
		self.addCleanup(_clear_rows)
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.cache.delete_keys("rl:")
		self.addCleanup(frappe.cache.delete_keys, "rl:")

	def use(self, patcher):
		patcher.start()
		self.addCleanup(patcher.stop)

	def message(self, tag):
		return contact.submit("Ravi", email(tag), "hello")

	def join(self, tag):
		return waitlist.join(email(tag))

	def register(self, tag):
		return signup.sign_up(email(tag), "Test Person")

	def exhaust(self, form):
		"""Spend one endpoint's whole allowance from this address, on a fresh email each time."""
		for attempt in range(throttle.PER_ADDRESS_HOURLY):
			form(attempt)
		with self.assertRaises(frappe.RateLimitExceededError):
			form("over")

	def post_back(self, route, **fields) -> str:
		frappe.local.form_dict = frappe._dict(fields)
		self.addCleanup(setattr, frappe.local, "form_dict", frappe._dict())
		return get_response_content(route)

	def post_contact(self, tag) -> str:
		return self.post_back(CONTACT_ROUTE, name="Ravi", email=email(tag), message="hello")

	def post_signup(self, tag) -> str:
		return self.post_back(
			SIGNUP_ROUTE, full_name="Ravi", email=email(tag), company="Acme", expected_apps="erpnext"
		)

	def test_exhausting_the_contact_form_leaves_the_other_two_usable(self):
		with as_request():
			self.exhaust(self.message)

			self.assertTrue(self.join("waitlist")["joined"])
			self.assertEqual(self.register("signup")[0], 1)

	def test_exhausting_the_signup_form_leaves_the_contact_form_usable(self):
		with as_request():
			self.exhaust(self.register)

			self.assertTrue(self.message("contact")["sent"])

	def test_a_fresh_email_each_time_is_stopped_by_the_ceiling(self):
		with as_request():
			for attempt in range(throttle.PER_ADDRESS_HOURLY):
				self.message(attempt)

			with self.assertRaises(frappe.RateLimitExceededError):
				self.message("over")

	def test_the_ceiling_is_per_address(self):
		with as_request():
			self.exhaust(self.message)
		with as_request(OTHER_ADDRESS):
			self.assertTrue(self.message("elsewhere")["sent"])

	def test_the_keyed_limit_still_stops_a_repeat_of_the_same_email(self):
		with as_request():
			for _attempt in range(contact.MESSAGES_PER_HOUR):
				self.message("same")

			with self.assertRaises(frappe.RateLimitExceededError):
				self.message("same")

	def test_one_visitor_using_every_form_is_never_limited(self):
		with as_request():
			for _attempt in range(contact.MESSAGES_PER_HOUR):
				self.assertTrue(self.message("visitor")["sent"])
			for _attempt in range(waitlist.JOINS_PER_HOUR):
				self.assertTrue(self.join("visitor")["joined"])
			for _attempt in range(signup.SIGNUPS_PER_HOUR):
				self.assertEqual(self.register("visitor")[0], 1)

	def test_a_post_back_spends_the_same_counter_and_only_that_one(self):
		frappe.set_user("Guest")
		with as_request():
			self.exhaust(self.message)

			self.assertIn(TOO_MANY, self.post_contact("postback"))
			self.assertNotIn(TOO_MANY, self.post_signup("postback"))
