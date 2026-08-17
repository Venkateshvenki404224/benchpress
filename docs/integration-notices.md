# Integration notices

Frappe apps and services BenchPress integrates with directly, and what our exposure to each one
is. Hand-maintained, because it records judgement rather than metadata.

The redistributed Python and npm dependency trees are a separate, generated list —
[THIRD-PARTY-NOTICES.md](../THIRD-PARTY-NOTICES.md).

## razorpay_frappe — optional

| | |
|---|---|
| Source | <https://github.com/bwhtech/razorpay_frappe> |
| Licence | MIT |
| Used by | [benchpress/credits/payments.py](benchpress/credits/payments.py) |
| Required | **No.** Deliberately absent from `required_apps` in [hooks.py](benchpress/hooks.py). |

Provides the `Razorpay Order` and `Razorpay Settings` DocTypes, order creation, the checkout
success/failure callbacks and webhook signature verification. BenchPress uses **Razorpay Orders
only** — no Payment Links, no Subscriptions. Frappe v16 ships nothing of its own here: every
built-in payment gateway was removed in v14 by
`frappe/patches/v14_0/delete_payment_gateways.py`.

### Why it is optional

A self-hoster running BenchPress on their own hardware must never be made to install a payment
processor to use it. The integration is gated on `payments.payments_available()`, which asks
`frappe.get_installed_apps()`, and the only coupling is one `doc_events` entry on a DocType that
simply does not exist on a site without the app — an inert hook rather than a broken one.

### Maintenance exposure

It is a small project (roughly a dozen stars and under a hundred commits at the time of writing)
maintained by one author. That risk is accepted for a specific reason: the licence is MIT, so if
it stops being maintained we may fork or vendor it outright without relicensing anything.

Two properties keep that option cheap, and both should survive any future change here:

- **The seam is one doc event.** `Razorpay Order.on_update` is the entire contract BenchPress
  depends on. A fork, a vendored copy or a replacement gateway only has to keep a document whose
  status becomes `Paid`.
- **BenchPress does not trust its numbers.** `razorpay_frappe` exposes an open
  `/razorpay-api/initiate-order` endpoint on which any logged-in caller names their own amount and
  metadata, so settlement re-reads every price from BenchPress's own `Credit Pack` and
  `Credit Settings` records and credits nothing unless the rupees paid match. Swapping the gateway
  changes where a payment is confirmed, never what it is worth.

### Transitive

`razorpay_frappe` depends on the official [`razorpay`](https://github.com/razorpay/razorpay-python)
Python SDK (MIT). BenchPress never imports it directly.

## vpn_management — required

| | |
|---|---|
| Source | <https://github.com/Venkateshvenki404224/vpn_management> |
| Licence | Same as BenchPress |
| Required | Yes — listed in `required_apps`. |

The entire VPN plane (peers, IP allocation, `wg-agent`) is delegated to it. Maintained alongside
BenchPress, so it is a sibling rather than a third party in the usual sense; it is listed here
because it is a separate installable app with its own repository.
