# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""Phase 7: the waitlist is retired and anyone may sign up. What that must not cost us.

The free grant is the asset under attack here, so most of these tests are about the moment it is
posted rather than the amount. Three properties carry the phase:

- **Once ever, per address.** Not once per signup, not once per login — `Credit Account` is named
  after the email, so a second arrival by any route finds the grant already made.
- **Only after the address is proved.** An OAuth flow proves it at insert; an email signup proves
  it at first login, because `sign_up` sets a password the user never sees. A `User` row on its
  own proves nothing and must buy nothing.
- **Two doors, never both open.** `waitlist_open` decides which of `waitlist.join` and
  `signup.sign_up` accepts a stranger, and the other one refuses.

The concurrency cap's mechanics belong to `test_credit_guard`; what is asserted here is only the
part phase 7 introduces — that somebody who arrived through signup and has bought nothing sits on
the free ceiling, and is told the number when it stops them.

**Nothing in this module commits.** `IntegrationTestCase` rolls back once per class, so a single
commit would make every retuned setting in it durable on the site.
"""

import json
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime

from benchpress import signup, waitlist
from benchpress.credits import account, admission, guard, onboarding
from benchpress.credits.onboarding import ACCESS_ROLE

ACCOUNT = "Credit Account"
LEDGER = "Credit Ledger Entry"
WAITLIST = "Waitlist Entry"
BENCHPRESS_SETTINGS = "BenchPress Settings"
CREDIT_SETTINGS = "Credit Settings"
WEBSITE_SETTINGS = "Website Settings"

EMAIL = "signup-test@example.com"
OAUTH_EMAIL = "signup-oauth@example.com"
DESK_EMAIL = "signup-desk@example.com"
NOTIFIED_EMAIL = "signup-notified@example.com"
BLOCKED_DOMAIN = "signup-throwaway.example"
BLOCKED_EMAIL = f"nobody@{BLOCKED_DOMAIN}"

# Enough of `waitlist.announce_signup`'s subject to tell the one-shot apart from the other mail
# the same address now gets. Keep in step with `benchpress/waitlist.py`.
RETIREMENT_SUBJECT = "Hosted BenchPress is open"
EVERY_EMAIL = (EMAIL, OAUTH_EMAIL, DESK_EMAIL, NOTIFIED_EMAIL, BLOCKED_EMAIL)

GRANT_CREDITS = 40.0
FREE_CEILING = 2
PAID_CEILING = 9

# Every setting this module retunes, snapshotted once and written back before each test — the
# class-level rollback is too late to keep siblings independent of each other.
TUNED_SETTINGS = (
	"waitlist_open",
	"blocked_email_domains",
	"signup_grant_credits",
	"max_concurrent_free",
	"max_concurrent_paid",
)


def _login_as(email: str):
	"""The one attribute `on_session_creation` hands its hooks."""
	return frappe._dict(user=email)


def _insert_oauth_user(email: str):
	"""A user shaped the way `frappe.utils.oauth` shapes one: a provider row, present at insert."""
	user = frappe.new_doc("User")
	user.update({"email": email, "first_name": "OAuth Person", "send_welcome_email": 0})
	user.append("social_logins", {"provider": "github", "userid": "424242"})
	return user.insert(ignore_permissions=True)


def _insert_desk_user(email: str):
	"""What an operator creating a colleague's account looks like — a System User, not a signup."""
	user = frappe.new_doc("User")
	user.update({"email": email, "first_name": "Desk Person", "send_welcome_email": 0})
	user.append("roles", {"role": "System Manager"})
	return user.insert(ignore_permissions=True)


def _roles_of(email: str) -> list[str]:
	return [row.role for row in frappe.get_doc("User", email).roles]


class TestSelfServeSignup(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.switch_at_start = frappe.db.get_single_value(BENCHPRESS_SETTINGS, "enable_credits")
		cls.settings_at_start = {
			field: frappe.db.get_single_value(CREDIT_SETTINGS, field) for field in TUNED_SETTINGS
		}
		cls.signup_disabled_at_start = frappe.db.get_single_value(WEBSITE_SETTINGS, "disable_signup")

	def setUp(self):
		frappe.set_user("Administrator")
		self.silence_outgoing_mail()
		self.restore_settings()
		self.set_credits_enabled(1)
		self.open_signup()
		self.wipe_people()
		self.addCleanup(self.wipe_people)
		self.addCleanup(frappe.set_user, "Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")

	# --- Fixtures -------------------------------------------------------------

	def silence_outgoing_mail(self) -> None:
		"""Signup sends a verification mail, which must not leave the test.

		Muting alone is not enough — the send runs after commit, so on a site with no Email Account
		it surfaces inside whichever *later* test commits first. Patching the send means no Email
		Queue row is written at all. `None`, not a mock: `send_welcome_mail_to_user` reads
		`.message` off what this returns when there is a document.
		"""
		mailer = patch("frappe.sendmail", return_value=None)
		self.mailer = mailer.start()
		self.addCleanup(mailer.stop)
		self.addCleanup(setattr, frappe.flags, "mute_emails", frappe.flags.mute_emails)
		frappe.flags.mute_emails = True

	def restore_settings(self) -> None:
		for field, value in self.settings_at_start.items():
			self.set_setting(field, value)
		self.set_signup_disabled(self.signup_disabled_at_start)
		self.set_credits_enabled(self.switch_at_start)

	def open_signup(self) -> None:
		"""The phase-7 world: the waitlist retired, self-serve signup live.

		Both switches are written directly because `set_single_value` skips `on_update` — the test
		that asserts the second one *follows* the first saves the document instead, so this fixture
		cannot pass that test by accident.
		"""
		self.set_setting("waitlist_open", 0)
		self.set_signup_disabled(0)
		self.set_setting("signup_grant_credits", GRANT_CREDITS)

	def set_signup_disabled(self, value) -> None:
		frappe.db.set_single_value(WEBSITE_SETTINGS, "disable_signup", value)
		frappe.clear_cache(doctype=WEBSITE_SETTINGS)

	def set_credits_enabled(self, value) -> None:
		frappe.db.set_single_value(BENCHPRESS_SETTINGS, "enable_credits", value)
		frappe.clear_cache(doctype=BENCHPRESS_SETTINGS)

	def set_setting(self, field: str, value) -> None:
		frappe.db.set_single_value(CREDIT_SETTINGS, field, value)
		frappe.clear_cache(doctype=CREDIT_SETTINGS)

	def wipe_people(self) -> None:
		"""Credit rows first: `Credit Account.user` links the `User` being deleted.

		Scoped to this module's addresses, because a dev site can already hold real accounts.
		"""
		for email in EVERY_EMAIL:
			frappe.db.delete(LEDGER, {"account": email})
			frappe.db.delete(ACCOUNT, {"user": email})
			for doctype in (WAITLIST, "User"):
				if frappe.db.exists(doctype, email):
					frappe.delete_doc(doctype, email, force=True, ignore_permissions=True)

	# --- Assertions the whole module shares -----------------------------------

	def mails_to(self, email: str) -> int:
		"""Retirement notices sent to one address, counted by subject."""
		# Matched on the subject, not just the recipient: `waitlist.join` now also acknowledges the
		# request to the same address (spec §6.1), and this count is about the one-shot alone.
		return len(
			[
				call
				for call in self.mailer.call_args_list
				if call.kwargs["recipients"] == [email] and RETIREMENT_SUBJECT in call.kwargs["subject"]
			]
		)

	def assert_granted_once(self, email: str) -> None:
		grants = frappe.get_all(
			LEDGER, filters={"account": email, "entry_type": account.GRANT}, fields=["credits"]
		)
		self.assertEqual(len(grants), 1, "the signup grant must be posted exactly once, ever")
		self.assertEqual(grants[0].credits, GRANT_CREDITS)
		self.assertEqual(frappe.db.get_value(ACCOUNT, email, "balance"), GRANT_CREDITS)

	# --- The grant follows proof of the address -------------------------------

	def test_an_email_signup_gets_the_app_role_but_no_grant_yet(self):
		signup.sign_up(EMAIL, "Test Person")

		self.assertIn(ACCESS_ROLE, _roles_of(EMAIL))
		self.assertFalse(
			frappe.db.exists(ACCOUNT, EMAIL),
			"a typed-in address is not a proved one, so it must not hold credits yet",
		)

	def test_the_grant_lands_on_first_login_with_exactly_the_configured_amount(self):
		signup.sign_up(EMAIL, "Test Person")

		onboarding.after_login(_login_as(EMAIL))

		self.assert_granted_once(EMAIL)

	def test_a_second_login_grants_nothing_further(self):
		signup.sign_up(EMAIL, "Test Person")
		onboarding.after_login(_login_as(EMAIL))

		onboarding.after_login(_login_as(EMAIL))

		self.assert_granted_once(EMAIL)

	def test_a_second_signup_with_the_same_address_grants_nothing_further(self):
		signup.sign_up(EMAIL, "Test Person")
		onboarding.after_login(_login_as(EMAIL))

		code, message = signup.sign_up(EMAIL, "Test Person")

		self.assertEqual(code, 0, message)
		self.assert_granted_once(EMAIL)

	def test_an_oauth_signup_is_granted_the_moment_the_user_is_created(self):
		"""A provider row present at insert *is* the proof, so this path needs no login."""
		_insert_oauth_user(OAUTH_EMAIL)

		self.assertIn(ACCESS_ROLE, _roles_of(OAUTH_EMAIL))
		self.assert_granted_once(OAUTH_EMAIL)

	def test_frappes_own_internal_social_login_row_is_not_read_as_oauth(self):
		"""`User.validate` gives every user a `frappe` provider row, so it cannot mean anything.

		Without this exclusion an ordinary email signup would look like a completed OAuth flow and
		be granted before the address had been proved at all — which is the whole control.
		"""
		signup.sign_up(EMAIL, "Test Person")

		providers = {row.provider for row in frappe.get_doc("User", EMAIL).social_logins}
		self.assertEqual(providers, {onboarding.INTERNAL_PROVIDER})
		self.assertFalse(frappe.db.exists(ACCOUNT, EMAIL))

	def test_a_login_by_somebody_without_the_app_role_opens_no_account(self):
		_insert_desk_user(DESK_EMAIL)

		onboarding.after_login(_login_as(DESK_EMAIL))

		self.assertFalse(frappe.db.exists(ACCOUNT, DESK_EMAIL), "an operator is not a customer")

	def test_a_desk_user_created_by_an_operator_gets_no_app_role(self):
		_insert_desk_user(DESK_EMAIL)

		self.assertNotIn(ACCESS_ROLE, _roles_of(DESK_EMAIL))

	# --- The switch off means none of this exists -----------------------------

	def test_no_role_and_no_grant_when_credits_are_off(self):
		self.set_credits_enabled(0)

		signup.sign_up(EMAIL, "Test Person")
		onboarding.after_login(_login_as(EMAIL))

		self.assertNotIn(ACCESS_ROLE, _roles_of(EMAIL))
		self.assertFalse(frappe.db.exists(ACCOUNT, EMAIL))

	def test_the_waitlist_switch_is_not_consulted_when_credits_are_off(self):
		"""A self-hoster's login page must keep working whatever the hosted flags say."""
		self.set_setting("waitlist_open", 1)
		self.set_credits_enabled(0)

		code, message = signup.sign_up(EMAIL, "Test Person")

		self.assertNotEqual(code, 0, message)
		self.assertTrue(frappe.db.exists("User", EMAIL))

	def test_the_fixture_can_put_the_switch_back_where_it_found_it(self):
		"""Every test here forces credits on, so the restore path is what has to be trustworthy.

		`IntegrationTestCase` rolls back once per class, which is only enough because nothing in
		this module commits — and if something ever does, this is the path that saves the site.
		"""
		self.restore_settings()

		self.assertEqual(
			frappe.db.get_single_value(BENCHPRESS_SETTINGS, "enable_credits"),
			self.switch_at_start,
		)

	# --- Abuse controls -------------------------------------------------------

	def test_a_blocklisted_domain_is_refused(self):
		self.set_setting("blocked_email_domains", f"{BLOCKED_DOMAIN}\nmailinator.com")

		with self.assertRaises(frappe.ValidationError):
			signup.sign_up(BLOCKED_EMAIL, "Nobody")

		self.assertFalse(frappe.db.exists("User", BLOCKED_EMAIL))

	def test_an_unlisted_domain_still_gets_through(self):
		self.set_setting("blocked_email_domains", f"{BLOCKED_DOMAIN}\nmailinator.com")

		code, message = signup.sign_up(EMAIL, "Test Person")

		self.assertNotEqual(code, 0, message)
		self.assertTrue(frappe.db.exists("User", EMAIL))

	def test_the_blocklist_ignores_case_and_a_leading_at(self):
		self.set_setting("blocked_email_domains", f"  @{BLOCKED_DOMAIN.upper()}  ")

		with self.assertRaises(frappe.ValidationError):
			signup.sign_up(BLOCKED_EMAIL, "Nobody")

	def test_the_fourth_signup_in_an_hour_is_rate_limited(self):
		with _as_request(EMAIL):
			for _attempt in range(signup.SIGNUPS_PER_HOUR):
				signup.sign_up(EMAIL, "Test Person")
			with self.assertRaises(frappe.RateLimitExceededError):
				signup.sign_up(EMAIL, "Test Person")

	def test_a_signed_up_user_sits_on_the_free_ceiling_until_they_buy(self):
		self.set_setting("max_concurrent_free", FREE_CEILING)
		self.set_setting("max_concurrent_paid", PAID_CEILING)
		signup.sign_up(EMAIL, "Test Person")
		onboarding.after_login(_login_as(EMAIL))

		frappe.set_user(EMAIL)

		self.assertEqual(guard.concurrency_limit(EMAIL), FREE_CEILING)

	def test_the_free_ceiling_refusal_names_the_number(self):
		"""`test_admission` owns the claim; what matters here is that the user is told why."""
		self.set_setting("max_concurrent_free", FREE_CEILING)
		signup.sign_up(EMAIL, "Test Person")
		frappe.set_user(EMAIL)

		account.ensure_account(EMAIL)
		frappe.db.set_value("Credit Account", EMAIL, "active_instances", FREE_CEILING, update_modified=False)
		with self.assertRaises(frappe.ValidationError) as refusal:
			admission.claim(EMAIL, "signup-ceiling-bench", FREE_CEILING)

		self.assertIn(str(FREE_CEILING), str(refusal.exception))

	# --- One door at a time ---------------------------------------------------

	def test_retiring_the_waitlist_clears_frappes_own_signup_switch(self):
		"""One decision, two fields — `disable_signup` gates the email form *and* both providers."""
		self.set_signup_disabled(1)

		self.save_waitlist_open(0)

		self.assertEqual(frappe.db.get_single_value(WEBSITE_SETTINGS, "disable_signup"), 0)

	def test_reopening_the_waitlist_puts_frappes_signup_switch_back(self):
		self.set_signup_disabled(0)

		self.save_waitlist_open(1)

		self.assertEqual(frappe.db.get_single_value(WEBSITE_SETTINGS, "disable_signup"), 1)

	def test_a_site_without_credits_keeps_its_own_signup_switch(self):
		self.set_signup_disabled(0)
		self.set_credits_enabled(0)

		self.save_waitlist_open(1)

		self.assertEqual(frappe.db.get_single_value(WEBSITE_SETTINGS, "disable_signup"), 0)

	def save_waitlist_open(self, value) -> None:
		"""Through the document, so `on_update` runs — that is what is under test here."""
		settings = frappe.get_doc(CREDIT_SETTINGS)
		settings.waitlist_open = value
		settings.save(ignore_permissions=True)
		frappe.clear_cache(doctype=CREDIT_SETTINGS)

	def test_signup_is_refused_while_the_waitlist_is_still_open(self):
		self.set_setting("waitlist_open", 1)

		with self.assertRaises(frappe.ValidationError):
			signup.sign_up(EMAIL, "Test Person")

		self.assertFalse(frappe.db.exists("User", EMAIL))

	def test_the_waitlist_is_refused_once_signup_has_replaced_it(self):
		with self.assertRaises(frappe.ValidationError):
			waitlist.join(EMAIL)

		self.assertFalse(frappe.db.exists(WAITLIST, EMAIL))

	def test_the_waitlist_still_accepts_while_it_is_open(self):
		self.set_setting("waitlist_open", 1)

		self.assertTrue(waitlist.join(EMAIL)["joined"])

	def test_a_retirement_notice_goes_out_once_per_entry(self):
		"""Once per *entry*, so the count that matters is per address, not the site-wide total.

		`notify_of_signup` mails every un-invited row on the waitlist, and a dev site holds real
		ones. The already-invited entry is the control: it proves the one-shot is stored on the row
		rather than inferred from the run.
		"""
		self.set_setting("waitlist_open", 1)
		waitlist.join(EMAIL)
		waitlist.join(NOTIFIED_EMAIL)
		invited_on = now_datetime()
		frappe.db.set_value(WAITLIST, NOTIFIED_EMAIL, "invite_sent_on", invited_on, update_modified=False)
		self.set_setting("waitlist_open", 0)

		waitlist.notify_of_signup()
		waitlist.notify_of_signup()

		self.assertEqual(self.mails_to(EMAIL), 1, "an operator re-running this must not mail anybody twice")
		self.assertEqual(self.mails_to(NOTIFIED_EMAIL), 0, "an invited entry is never mailed again")
		self.assertIsNotNone(frappe.db.get_value(WAITLIST, EMAIL, "invite_sent_on"))
		self.assertEqual(frappe.db.get_value(WAITLIST, NOTIFIED_EMAIL, "invite_sent_on"), invited_on)

	def test_the_retirement_notice_is_denied_to_a_non_admin(self):
		frappe.set_user("Guest")

		with self.assertRaises(frappe.PermissionError):
			waitlist.notify_of_signup()


class _as_request:
	"""Make the rate limiter apply — it is a no-op outside an HTTP request.

	The decorator keys on the request IP and the `email` form field, so a direct function call
	would sail past it and the limit would never be exercised.
	"""

	def __init__(self, email):
		self.email = email

	def __enter__(self):
		frappe.cache.delete_keys("rl:")
		frappe.local.request = MagicMock(method="POST")
		frappe.local.request_ip = "127.0.0.1"
		frappe.local.form_dict = frappe._dict(cmd="benchpress.signup.sign_up", email=self.email)
		return self

	def __exit__(self, *exception):
		frappe.cache.delete_keys("rl:")
		frappe.local.request = None
		frappe.local.form_dict = frappe._dict()
		return False
