# Integration notices

Third-party work BenchPress ships or depends on that no dependency scanner can see: the Frappe
apps it integrates with, and the web fonts it vendors. Hand-maintained, because it records
judgement rather than metadata.

The redistributed Python and npm dependency trees are a separate, generated list —
[THIRD-PARTY-NOTICES.md](../THIRD-PARTY-NOTICES.md).

## Bundled fonts

| Family | Source | Licence | Where |
|---|---|---|---|
| Poppins | <https://github.com/itfoundry/Poppins> | OFL-1.1 | Landing page chrome — `benchpress/public/fonts/` |
| Inter | <https://github.com/rsms/inter> | OFL-1.1 | Product mocks on the landing page, and the docs page — `benchpress/public/fonts/`, `docs/fonts/` |
| JetBrains Mono | <https://github.com/JetBrains/JetBrainsMono> | OFL-1.1 | Terminal blocks on the docs page — `docs/fonts/` |

The Vue SPA is not in that table. It gets Inter from `frappe-ui`, which vendors the font itself,
so the app already had no external font request.

### Why they are vendored

These three used to load from `fonts.googleapis.com`. A BenchPress instance reachable only over
WireGuard cannot reach Google, so the pages rendered in system sans on exactly the deployments the
product is built for. Serving them ourselves also stops handing a visitor's IP address to a CDN on
every page load, which is the part that carries regulatory weight in the EU.

### What the licence requires

OFL-1.1 permits redistribution, bundling and modification. Two obligations follow us:

- **The licence text ships with the fonts.** `OFL-*.txt` sits in each directory next to the
  `.woff2` files it covers. Adding a font family means adding its licence file in the same commit.
- **The files must not be sold on their own.** They are not; they are part of a web page.

None of the three declares a Reserved Font Name in its copyright line, so the subsets we ship keep
the original family names. That matters because every file here **is** a subset — these are
Google's own `latin`, `latin-ext` and `devanagari` cuts, not the upstream releases — and a
reserved name would have forced us to rename the family in the CSS.

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
