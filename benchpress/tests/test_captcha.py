# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""Turnstile on the guest forms: absent without keys, and never the reason a real request is lost."""

from unittest.mock import MagicMock, patch

import frappe
import requests
from frappe.tests import IntegrationTestCase
from frappe.website.serve import get_response_content

import benchpress
from benchpress import captcha, contact, waitlist
from benchpress.credits import config
from benchpress.public_site import CONFIG_KEY
from benchpress.tests.guest_request import as_request

# Cloudflare's published always-pass test keys. Nothing here reaches Cloudflare: `requests.post` is mocked.
SITE = "1x00000000000000000000AA"
SECRET = "1x0000000000000000000000000000000AA"
KEYS = {captcha.SITE_KEY: SITE, captcha.SECRET_KEY: SECRET}

TOKEN = "test-token"
EMAIL = "captcha-test@example.com"
ADDRESS = "198.51.100.20"
REFUSED = "We could not confirm a person sent this"
# Each route with a marker only its form renders, so an error page cannot pass for a page without the widget.
FORM_ROUTES = {"/signup": "data-bp-signup-form", "/contact": "data-bp-contact-form"}


def verdict(**answer) -> MagicMock:
	return MagicMock(json=MagicMock(return_value=answer))


def _clear_rows():
	for doctype in ("Contact Message", "Waitlist Entry"):
		for name in frappe.get_all(doctype, filters={"email": EMAIL}, pluck="name"):
			frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)


class TestCaptcha(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")
		self.post = self.use(patch.object(captcha.requests, "post", return_value=verdict(success=True)))
		self.log = self.use(patch.object(frappe, "log_error"))
		self.use(patch.dict(frappe.local.conf, {CONFIG_KEY: 1}))
		self.use(patch.object(benchpress, "emails", MagicMock(), create=True))
		self.use(patch.object(waitlist, "send_notice", MagicMock()))
		self.use(patch.object(config, "credits_enabled", return_value=False))
		_clear_rows()
		self.addCleanup(_clear_rows)
		frappe.cache.delete_keys("rl:")
		self.addCleanup(frappe.cache.delete_keys, "rl:")
		self.previous_form = frappe.local.form_dict
		self.addCleanup(setattr, frappe.local, "form_dict", self.previous_form)
		self.posted(**{captcha.TOKEN_FIELD: TOKEN})

	def use(self, patcher):
		mock = patcher.start()
		self.addCleanup(patcher.stop)
		return mock

	def with_keys(self):
		self.use(patch.dict(frappe.local.conf, KEYS))

	def posted(self, **fields):
		frappe.local.form_dict = frappe._dict(fields)

	def render(self, route: str) -> str:
		with as_request(path=route, method="GET"):
			return get_response_content(route)

	def assert_refused(self, call, *args):
		with self.assertRaisesRegex(frappe.ValidationError, REFUSED):
			call(*args)

	# --- the check ---------------------------------------------------------------------------

	def test_without_keys_nothing_is_checked(self):
		self.posted()
		self.assertEqual(captcha.site_key(), "")
		with as_request():
			captcha.require_human()
		self.post.assert_not_called()

	def test_a_site_key_without_its_secret_turns_nothing_on(self):
		self.use(patch.dict(frappe.local.conf, {captcha.SITE_KEY: SITE}))
		self.assertEqual(captcha.site_key(), "")

	def test_outside_a_request_nothing_is_checked(self):
		self.with_keys()
		self.posted()
		captcha.require_human()
		self.post.assert_not_called()

	def test_a_missing_token_is_refused_before_any_outbound_call(self):
		self.with_keys()
		self.posted()
		with as_request():
			self.assert_refused(captcha.require_human)
		self.post.assert_not_called()

	def test_a_token_cloudflare_accepts_passes(self):
		self.with_keys()
		with as_request(ADDRESS):
			captcha.require_human()

		self.assertEqual(self.post.call_args.args, (captcha.VERIFY_URL,))
		sent = self.post.call_args.kwargs
		self.assertEqual(sent["data"], {"secret": SECRET, "response": TOKEN, "remoteip": ADDRESS})
		self.assertEqual(sent["timeout"], captcha.TIMEOUT)

	def test_a_token_cloudflare_rejects_is_refused(self):
		self.with_keys()
		for code in ("invalid-input-response", "timeout-or-duplicate"):
			with self.subTest(code=code):
				self.post.return_value = verdict(success=False, **{"error-codes": [code]})
				with as_request():
					self.assert_refused(captcha.require_human)
		self.log.assert_not_called()

	def test_no_verdict_lets_the_post_through_and_logs(self):
		self.with_keys()
		not_json = MagicMock(json=MagicMock(side_effect=ValueError("not json")))
		cases = {
			"unreachable": {"side_effect": requests.ConnectionError()},
			"slow": {"side_effect": requests.Timeout()},
			"not json": {"side_effect": None, "return_value": not_json},
		}
		for case, behaviour in cases.items():
			with self.subTest(case):
				self.post.configure_mock(**behaviour)
				with as_request():
					captcha.require_human()
		self.assertEqual(self.log.call_count, len(cases))

	def test_a_fault_on_our_side_lets_the_post_through_and_logs(self):
		self.with_keys()
		for code in sorted(captcha.NOT_THE_VISITOR):
			with self.subTest(code=code):
				self.post.return_value = verdict(success=False, **{"error-codes": [code]})
				with as_request():
					captcha.require_human()
				self.assertIn(code, self.log.call_args.kwargs["message"])

	# --- the forms ---------------------------------------------------------------------------

	def test_both_endpoints_refuse_a_missing_token_and_write_nothing(self):
		self.with_keys()
		self.posted()
		with as_request():
			self.assert_refused(waitlist.join, EMAIL)
			self.assert_refused(contact.submit, "Ravi", EMAIL, "hello")

		self.assertFalse(frappe.db.exists("Waitlist Entry", {"email": EMAIL}))
		self.assertFalse(frappe.db.exists("Contact Message", {"email": EMAIL}))

	def test_both_endpoints_record_a_request_cloudflare_vouches_for(self):
		self.with_keys()
		with as_request():
			self.assertTrue(waitlist.join(EMAIL)["joined"])
			self.assertTrue(contact.submit("Ravi", EMAIL, "hello")["sent"])
		self.assertEqual(self.post.call_count, 2)

	def test_an_api_post_carries_the_token_past_the_signature_filter(self):
		# `/api/method` dispatches through `frappe.call`, which drops every field the endpoint does not declare.
		self.with_keys()
		self.posted(**{"email": EMAIL, "csrf_token": "x", captcha.TOKEN_FIELD: TOKEN})
		with as_request():
			self.assertTrue(frappe.call(waitlist.join, **frappe.local.form_dict)["joined"])
		self.assertEqual(self.post.call_args.kwargs["data"]["response"], TOKEN)

	def test_the_widget_renders_on_both_forms_only_with_keys(self):
		frappe.set_user("Guest")
		for route, form in FORM_ROUTES.items():
			with self.subTest(route=route, keys=False):
				html = self.render(route)
				self.assertIn(form, html)
				self.assertNotIn("data-bp-captcha", html)

		self.with_keys()
		for route, form in FORM_ROUTES.items():
			with self.subTest(route=route, keys=True):
				html = self.render(route)
				self.assertIn(form, html)
				self.assertIn(f'data-bp-captcha data-sitekey="{SITE}"', html)
				self.assertIn("onload=bpRenderCaptchas", html)
				self.assertNotIn(SECRET, html)

	def test_a_page_post_back_without_a_token_shows_the_refusal(self):
		self.with_keys()
		frappe.set_user("Guest")
		self.posted(full_name="Ravi", email=EMAIL, company="Acme", expected_apps="erpnext", consented="1")
		with as_request(path="/signup"):
			html = get_response_content("/signup")

		self.assertIn(FORM_ROUTES["/signup"], html)
		self.assertIn(REFUSED, html)
		self.assertFalse(frappe.db.exists("Waitlist Entry", {"email": EMAIL}))
