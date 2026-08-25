# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""Phase 6 takes money, so the assertions here are about the two ways that goes wrong.

**Paying twice for one payment.** Razorpay retries webhooks, `on_update` fires on every save of
an order, and an operator pressing *Sync Status* is a third delivery. So the central test replays
the same paid order three times and insists the balance moved once. A gateway integration that is
only correct when every message arrives exactly once is not correct.

**Being paid a rupee for a thousand credits.** `razorpay_frappe` ships an open
`/razorpay-api/initiate-order` endpoint where the caller names their own amount and references, so
an order is not evidence of what was bought. The settlement tests therefore forge orders — right
pack, wrong price; somebody else's instance — and insist nothing is credited.

Everything that needs a `Razorpay Order` skips when the app is absent, because that is a supported
state rather than a broken one. `TestPaymentsWithoutGateway` is the test that runs either way, and
it is the one a self-hoster's CI is actually asserting.
"""

import unittest
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, flt, getdate, today

from benchpress import api
from benchpress.benchpress.doctype.bench_instance import get_instance_id
from benchpress.credits import account, config, metering, passes, payments
from benchpress.credits.seed import seed_defaults

ACCOUNT = "Credit Account"
LEDGER = "Credit Ledger Entry"
BENCHPRESS_SETTINGS = "BenchPress Settings"
PASS = "Always On Pass"

# The seeded "Small" size and "Starter" pack.
GRANT = 40.0
PACK = "Starter"
PACK_PRICE = 499
PACK_CREDITS = 200.0
PASS_PRICE = 999

USER = "payments-owner@example.com"
STRANGER = "payments-stranger@example.com"

gateway_installed = unittest.skipUnless(
	payments.payments_available(), "razorpay_frappe is not installed on this bench"
)


def _ensure_user(email: str) -> str:
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Payments Owner",
				"send_welcome_email": 0,
				"roles": [{"role": "BenchPress User"}],
			}
		).insert(ignore_permissions=True)
	return email


def _ensure_lab(lab_id: str, owner: str):
	if frappe.db.exists("Lab", lab_id):
		frappe.delete_doc("Lab", lab_id, force=True, ignore_permissions=True)
	frappe.set_user(owner)
	try:
		return frappe.get_doc(
			{
				"doctype": "Lab",
				"lab_id": lab_id,
				"title": f"Payments {lab_id}",
				"frappe_version": "version-15",
				"image_tag": "benchpress/test:latest",
				"memory_limit": "1g",
				"cpu_cores": 1,
			}
		).insert(ignore_permissions=True)
	finally:
		frappe.set_user("Administrator")


def _ensure_bench(lab, owner: str, **extra):
	name = get_instance_id(owner, lab.name)
	if frappe.db.exists("Bench Instance", name):
		frappe.delete_doc("Bench Instance", name, force=True, ignore_permissions=True)
	frappe.set_user(owner)
	try:
		return frappe.get_doc(
			{
				"doctype": "Bench Instance",
				"lab": lab.name,
				"frappe_version": lab.frappe_version,
				"status": "Running",
				"container_id": "payments-container",
				**extra,
			}
		).insert(ignore_permissions=True)
	finally:
		frappe.set_user("Administrator")


class PaymentsFixture(IntegrationTestCase):
	"""One user, one lab, one instance, and a credit switch that is put back where it was found."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		seed_defaults()
		cls.switch_at_start = frappe.db.get_single_value(BENCHPRESS_SETTINGS, "enable_credits")
		cls.user = _ensure_user(USER)
		cls.stranger = _ensure_user(STRANGER)
		cls.lab = _ensure_lab("payments-lab", cls.user)
		cls.bench = _ensure_bench(cls.lab, cls.user)
		frappe.db.commit()  # nosemgrep -- class fixtures must outlive the per-test transaction

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		frappe.delete_doc("Bench Instance", cls.bench.name, force=True, ignore_permissions=True)
		frappe.delete_doc("Lab", cls.lab.name, force=True, ignore_permissions=True)
		cls.wipe()
		for email in (cls.user, cls.stranger):
			if frappe.db.exists("User", email):
				frappe.delete_doc("User", email, force=True, ignore_permissions=True)
		frappe.db.commit()  # nosemgrep -- fixtures were committed, so the cleanup must be too
		super().tearDownClass()

	def setUp(self):
		frappe.set_user("Administrator")
		config.clear_size_index()
		self.wipe()
		frappe.db.set_value(
			"Bench Instance",
			self.bench.name,
			{
				"credit_burn_rate": 0.0,
				"credit_burn_started": None,
				"status": "Running",
				"expires_at_ts": 0,
				"lease_state": "",
			},
			update_modified=False,
		)

	# --- Fixtures the assertions read ----------------------------------------

	def set_credits_enabled(self, value: int) -> None:
		"""One cleanup, not two: `addCleanup` runs LIFO, so a separate `clear_cache` would fire
		*before* the value was restored and leave the switch stuck on for every later test."""
		original = frappe.db.get_single_value(BENCHPRESS_SETTINGS, "enable_credits")
		self.addCleanup(self.write_switch, original)
		self.write_switch(value)

	def write_switch(self, value) -> None:
		frappe.db.set_single_value(BENCHPRESS_SETTINGS, "enable_credits", value)
		frappe.db.commit()  # nosemgrep -- the code under test commits, so the restore must too
		frappe.clear_cache()

	def set_pass_price(self, rupees) -> None:
		original = frappe.db.get_single_value("Credit Settings", "always_on_monthly_inr")
		self.addCleanup(self.write_pass_price, original)
		self.write_pass_price(rupees)

	def write_pass_price(self, rupees) -> None:
		frappe.db.set_single_value("Credit Settings", "always_on_monthly_inr", rupees)
		frappe.db.commit()  # nosemgrep -- committed for the same reason as the switch
		frappe.clear_cache()

	def balance(self) -> float:
		return flt(frappe.db.get_value(ACCOUNT, self.user, "balance"))

	def available(self) -> float:
		row = frappe.db.get_value(ACCOUNT, self.user, account.BALANCE_FIELDS, as_dict=True)
		return account.available(row)

	def entries(self, entry_type: str | None = None) -> list:
		filters = {"account": self.user}
		if entry_type:
			filters["entry_type"] = entry_type
		return frappe.get_all(
			LEDGER,
			filters=filters,
			fields=["name", "entry_type", "credits", "balance_after", "reference_name"],
			order_by="creation asc",
		)

	def ledger_sum(self) -> float:
		return flt(sum(flt(entry.credits) for entry in self.entries()), account.PRECISION)

	@classmethod
	def wipe(cls) -> None:
		"""The ledger blocks updates, not deletes — the suite still has to clean up after itself."""
		frappe.db.delete(PASS, {"bench_instance": cls.bench.name})
		for email in (USER, STRANGER):
			frappe.db.delete(LEDGER, {"account": email})
			frappe.db.delete(ACCOUNT, {"user": email})
		if payments.payments_available():
			frappe.db.delete(payments.ORDER, {"owner": ("in", [USER, STRANGER])})
		frappe.db.commit()  # nosemgrep -- fixture cleanup must outlive the per-test rollback


class TestPaymentsWithoutGateway(PaymentsFixture):
	"""The state a self-hoster is in: credits on, no payment app. Nothing may break."""

	def setUp(self):
		super().setUp()
		self.set_credits_enabled(1)

	def without_gateway(self):
		"""Simulate the app being absent whether or not this bench actually has it."""
		installed = [app for app in frappe.get_installed_apps() if app != payments.APP]
		return patch("frappe.get_installed_apps", return_value=installed)

	def test_buying_says_what_is_missing(self):
		with self.without_gateway(), self.assertRaises(frappe.ValidationError) as refusal:
			payments.buy_credits(PACK)
		self.assertIn(payments.APP, str(refusal.exception))

	def test_buying_a_pass_says_the_same_thing(self):
		self.set_pass_price(PASS_PRICE)
		with self.without_gateway(), self.assertRaises(frappe.ValidationError) as refusal:
			payments.buy_always_on_pass(self.bench.name)
		self.assertIn(payments.APP, str(refusal.exception))

	def test_prices_are_still_published(self):
		"""The packs are shown and marked unbuyable — a price list is not a checkout."""
		with self.without_gateway():
			options = payments.purchase_options()
		self.assertTrue(options["enabled"])
		self.assertFalse(options["payments_available"])
		self.assertTrue(any(pack.name == PACK for pack in options["packs"]))

	def test_the_rest_of_the_app_still_works(self):
		with self.without_gateway():
			account.grant(self.user, 10, "still working")
			self.assertEqual(account.summary(self.user)["balance"], GRANT + 10)

	def test_nothing_is_for_sale_when_credits_are_off(self):
		self.set_credits_enabled(0)
		self.assertEqual(
			payments.purchase_options(), {"enabled": False, "payments_available": False, "packs": []}
		)

	def test_an_inactive_pack_is_refused(self):
		"""Before the gateway is even consulted: a withdrawn pack is not a payment problem."""
		frappe.db.set_value("Credit Pack", PACK, "is_active", 0)
		self.addCleanup(frappe.db.set_value, "Credit Pack", PACK, "is_active", 1)
		frappe.clear_cache()
		with self.assertRaises(frappe.ValidationError) as refusal:
			payments.buy_credits(PACK)
		self.assertIn("not on sale", str(refusal.exception))

	def test_an_unknown_pack_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			payments.buy_credits("No Such Pack")


@gateway_installed
class TestOrderSettlement(PaymentsFixture):
	"""Everything that needs a real `Razorpay Order` row to exist."""

	def setUp(self):
		super().setUp()
		self.set_credits_enabled(1)

	# --- Fixtures --------------------------------------------------------------

	def order(self, ref_dt: str, ref_dn: str, amount, owner: str | None = None, status="Pending"):
		"""An order exactly as `RazorpayOrder.initiate` leaves one, without calling Razorpay."""
		frappe.set_user(owner or self.user)
		try:
			return frappe.get_doc(
				{
					"doctype": payments.ORDER,
					"order_id": frappe.generate_hash(length=14),
					"amount": amount,
					"currency": "INR",
					"status": status,
					"ref_dt": ref_dt,
					"ref_dn": ref_dn,
				}
			).insert(ignore_permissions=True)
		finally:
			frappe.set_user("Administrator")

	def pay(self, order) -> None:
		"""Mark it paid the way `mark_as_paid` does — as Administrator, which is the webhook."""
		order.status = "Paid"
		order.save(ignore_permissions=True)

	def pack_order(self, amount=PACK_PRICE, **kwargs):
		return self.order("Credit Pack", PACK, amount, **kwargs)

	def pass_order(self, amount=PASS_PRICE, bench=None, **kwargs):
		return self.order("Bench Instance", bench or self.bench.name, amount, **kwargs)

	# --- Crediting exactly once ------------------------------------------------

	def test_a_paid_pack_credits_the_balance(self):
		self.pay(self.pack_order())
		self.assertEqual(self.balance(), GRANT + PACK_CREDITS)
		purchases = self.entries(account.PURCHASE)
		self.assertEqual(len(purchases), 1)
		self.assertEqual(flt(purchases[0].credits), PACK_CREDITS)

	def test_replaying_the_same_webhook_credits_once(self):
		"""The central test of this phase. Three deliveries, one credit."""
		order = self.pack_order()
		self.pay(order)
		for _delivery in range(2):
			payments.on_razorpay_update(frappe.get_doc(payments.ORDER, order.name))
		self.assertEqual(self.balance(), GRANT + PACK_CREDITS)
		self.assertEqual(len(self.entries(account.PURCHASE)), 1)

	def test_a_pending_order_credits_nothing(self):
		self.pack_order()
		self.assertEqual(self.entries(account.PURCHASE), [])

	def test_a_failed_order_credits_nothing(self):
		order = self.pack_order()
		order.status = "Failed"
		order.save(ignore_permissions=True)
		self.assertEqual(self.entries(account.PURCHASE), [])

	def test_the_buyer_is_credited_not_the_session(self):
		"""A webhook is processed as Administrator; the money is the order owner's."""
		order = self.pack_order()
		frappe.set_user("Administrator")
		self.pay(order)
		self.assertEqual(self.balance(), GRANT + PACK_CREDITS)

	# --- Not trusting the order's numbers --------------------------------------

	def test_underpaying_for_a_pack_credits_nothing(self):
		"""The forged-order case: right pack, wrong price, straight from the open endpoint."""
		self.pay(self.pack_order(amount=1))
		self.assertEqual(self.entries(account.PURCHASE), [])
		self.assertEqual(self.balance(), 0.0)

	def test_an_order_referencing_nothing_credits_nothing(self):
		self.pay(self.order("User", self.user, PACK_PRICE))
		self.assertEqual(self.entries(account.PURCHASE), [])

	def test_a_pass_bought_for_somebody_elses_instance_credits_nothing(self):
		self.set_pass_price(PASS_PRICE)
		self.pay(self.pass_order(owner=self.stranger))
		self.assertFalse(passes.has_active_pass(self.bench.name))

	# --- Mid-burn ---------------------------------------------------------------

	def test_a_purchase_inside_a_lease_adds_credits_and_leaves_the_deadline_alone(self):
		"""A payment landing during a window must not shorten, extend or re-charge it."""
		bench = frappe.get_doc("Bench Instance", self.bench.name)
		metering.on_bench_running(bench)
		charged = self.balance()
		deadline = frappe.db.get_value("Bench Instance", self.bench.name, "expires_at_ts")
		self.assertTrue(deadline, "the lease never armed, so this proves nothing")

		self.pay(self.pack_order())

		self.assertAlmostEqual(self.available(), charged + PACK_CREDITS, places=4)
		self.assertEqual(frappe.db.get_value("Bench Instance", self.bench.name, "expires_at_ts"), deadline)
		self.assertAlmostEqual(self.ledger_sum(), self.balance(), places=4)

	# --- The always-on pass -----------------------------------------------------

	def test_a_paid_pass_exempts_the_instance(self):
		self.set_pass_price(PASS_PRICE)
		self.pay(self.pass_order())

		self.assertTrue(passes.has_active_pass(self.bench.name))
		granted = frappe.get_all(PASS, filters={"bench_instance": self.bench.name}, fields=["valid_until"])
		self.assertEqual(getdate(granted[0].valid_until), getdate(add_days(today(), config.PASS_DAYS)))

	def test_a_pass_clears_the_lease_clock(self):
		"""Prepaid time and leased time are the same time; selling both sells it twice."""
		self.set_pass_price(PASS_PRICE)
		metering.on_bench_running(frappe.get_doc("Bench Instance", self.bench.name))
		self.assertTrue(frappe.db.get_value("Bench Instance", self.bench.name, "expires_at_ts"))

		self.pay(self.pass_order())

		self.assertFalse(frappe.db.get_value("Bench Instance", self.bench.name, "expires_at_ts"))
		self.assertFalse(frappe.db.get_value("Bench Instance", self.bench.name, "lease_state"))

	def test_replaying_a_pass_webhook_grants_one_month(self):
		self.set_pass_price(PASS_PRICE)
		order = self.pass_order()
		self.pay(order)
		for _delivery in range(2):
			payments.on_razorpay_update(frappe.get_doc(payments.ORDER, order.name))
		self.assertEqual(frappe.db.count(PASS, {"bench_instance": self.bench.name}), 1)

	def test_a_pass_costs_no_credits(self):
		"""It buys hours, not credits — but it is still a Purchase row, so the money is recorded."""
		self.set_pass_price(PASS_PRICE)
		self.pay(self.pass_order())
		purchases = self.entries(account.PURCHASE)
		self.assertEqual(len(purchases), 1)
		self.assertEqual(flt(purchases[0].credits), 0.0)
		self.assertEqual(self.balance(), GRANT)

	def test_a_second_pass_cannot_be_bought_while_one_is_live(self):
		self.set_pass_price(PASS_PRICE)
		self.pay(self.pass_order())
		with self.assertRaises(frappe.ValidationError):
			payments.buy_always_on_pass(self.bench.name)

	# --- Refunds and adjustments -------------------------------------------------

	def test_purchase_spend_refund_reconciles_to_the_ledger(self):
		order = self.pack_order()
		self.pay(order)
		account.charge(self.user, 25, "a custom build")
		account.refund(self.user, 50, "half the pack, returned", (payments.ORDER, str(order.name)))

		self.assertEqual(self.balance(), GRANT + PACK_CREDITS - 25 - 50)
		self.assertAlmostEqual(self.ledger_sum(), self.balance(), places=4)
		self.assertEqual(
			flt(frappe.db.get_value(ACCOUNT, self.user, "lifetime_purchased")), PACK_CREDITS - 50
		)

	def test_a_refund_does_not_reopen_the_order(self):
		"""A redelivered webhook after a refund must not re-credit the same purchase."""
		order = self.pack_order()
		self.pay(order)
		account.refund(self.user, PACK_CREDITS, "returned", (payments.ORDER, str(order.name)))
		payments.on_razorpay_update(frappe.get_doc(payments.ORDER, order.name))
		self.assertEqual(self.balance(), GRANT)

	def test_the_reconciliation_report_shows_an_unsettled_order(self):
		from benchpress.benchpress.report.credit_reconciliation.credit_reconciliation import execute

		self.pay(self.pack_order(amount=1))
		rows = [row for row in execute()[1] if row["buyer"] == self.user]
		self.assertEqual([row["state"] for row in rows], ["Paid, not credited"])

	def test_the_reconciliation_report_shows_a_settled_order(self):
		from benchpress.benchpress.report.credit_reconciliation.credit_reconciliation import execute

		self.pay(self.pack_order())
		rows = [row for row in execute()[1] if row["buyer"] == self.user]
		self.assertEqual([row["state"] for row in rows], ["Settled"])


class TestLedgerIsEngineOnly(PaymentsFixture):
	"""The ledger explains a balance it never changed, so it refuses rows nobody's accounting made."""

	def setUp(self):
		super().setUp()
		self.set_credits_enabled(1)

	def test_a_hand_written_row_is_refused(self):
		account.ensure_account(self.user)
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{"doctype": LEDGER, "account": self.user, "entry_type": "Adjustment", "credits": 500}
			).insert(ignore_permissions=True)

	def test_an_adjustment_needs_a_reason(self):
		with self.assertRaises(frappe.ValidationError):
			account.adjust(self.user, 100, "   ")

	def test_an_adjustment_moves_the_balance_and_says_why(self):
		account.adjust(self.user, -10, "goodwill clawback")
		self.assertEqual(self.balance(), GRANT - 10)
		self.assertEqual(self.entries(account.ADJUSTMENT)[0].credits, -10)
		self.assertAlmostEqual(self.ledger_sum(), self.balance(), places=4)


class TestPurchaseEndpoints(PaymentsFixture):
	"""The whitelisted surface. A guest may not price anything, let alone buy it."""

	def setUp(self):
		super().setUp()
		self.set_credits_enabled(1)

	def test_options_need_an_app_role(self):
		frappe.set_user("Guest")
		self.addCleanup(frappe.set_user, "Administrator")
		with self.assertRaises(frappe.PermissionError):
			api.get_purchase_options()

	def test_buying_needs_an_app_role(self):
		frappe.set_user("Guest")
		self.addCleanup(frappe.set_user, "Administrator")
		with self.assertRaises(frappe.PermissionError):
			api.buy_credits(PACK)

	def test_a_pass_needs_access_to_the_instance(self):
		frappe.set_user(self.stranger)
		self.addCleanup(frappe.set_user, "Administrator")
		with self.assertRaises(frappe.PermissionError):
			api.buy_always_on_pass(self.bench.name)
