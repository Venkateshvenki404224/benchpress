# Self-serve Signup (hosted)

How to retire the waitlist and let anyone sign up. This applies to a **hosted** BenchPress —
`BenchPress Settings → Enable Credits` on. With credits off, none of it runs and your login page is
Frappe's unmodified one.

---

## The one switch

`Credit Settings → Self-serve Signup → Waitlist Open`.

| Waitlist Open | Landing page CTA | `waitlist.join` | `signup.sign_up` |
|---|---|---|---|
| On (default) | "Start free" → the waitlist form | accepts | refuses |
| Off | "Start free" → `/login#signup` | refuses | accepts |

Saving this field also writes `Website Settings → Disable Signup` to match, because that one field
gates all three signup methods — the email form *and*, through `provider_allows_signup`, both OAuth
providers. Turning the waitlist off with Disable Signup left on would put a "Start free" button in
front of a page Frappe refuses to render, so the second switch follows the first.

The `Waitlist Entry` doctype and every row in it are kept. Nothing is deleted by flipping the
switch.

---

## The three methods

All three land on the same thing: a `User` with the `BenchPress User` role and a `Credit Account`
holding `signup_grant_credits`.

### GitHub and Google — the primary paths

Frappe ships both. Create a **Social Login Key** per provider:

1. Register an OAuth app with the provider. Callback URL:
   `https://<your-domain>/api/method/frappe.integrations.oauth2_logins.login_via_github`
   (`…login_via_google` for Google).
2. In Desk, **Social Login Key → New**, pick the provider from *Social Login Provider*, paste the
   client id and secret.
3. Tick **Enable Social Login** and **Sign ups** (`Allow Sign-up`). Without the second one, an
   existing user can sign in but a new one cannot be created.
4. Save. The buttons appear on `/login` on the next request.

GitHub is the primary button on purpose. An aged GitHub account is evidence that the person is real
in a way a fresh email address is not, which is what makes the free grant safe to hand out without
a card.

### Email

Nothing to configure beyond an outgoing **Email Account** — the verification mail is what proves
the address. A site with no Email Account will create the user and then have no way to let them in.

---

## When the grant is posted

Never on the appearance of a `User` row. A row proves somebody typed an address, not that they hold
it, and free credits are what a throwaway-address farm is after. So:

- **OAuth signups** are granted at insert. `frappe.utils.oauth` writes the provider row before it
  saves the user, so the row itself is proof the flow completed.
- **Email signups** are granted at first login. `sign_up` sets a password the user never sees, so
  the only route to a session is the verification link.

Either way it happens exactly once ever: `Credit Account` is named after the email address, so a
second arrival by any route finds the account already open. A re-signup after an account was deleted
does **not** re-grant — that needs an operator's adjustment, on purpose.

---

## Abuse controls

| Control | Where | Default |
|---|---|---|
| Signups per hour, per (IP, address) | `benchpress.signup.SIGNUPS_PER_HOUR` | 3 |
| Signups per hour, site-wide | `System Settings → Max Signups Allowed Per Hour` | 300 |
| Disposable-domain blocklist | `Credit Settings → Blocked Email Domains` | empty |
| Concurrent instances before first purchase | `Credit Settings → Max Concurrent (Free)` | 2 |

**Blocked Email Domains** is one domain per line; a leading `@` and any casing are both fine. It is
checked on the email path only — an OAuth signup has already been vouched for by the provider, which
is the other reason to prefer those buttons.

The concurrency ceiling switches to `Max Concurrent (Paid)` the moment the account has a `Purchase`
ledger row. An Always On Pass counts as a purchase even though it posts zero credits.

---

## Telling the old waitlist

Once the switch is off, run this once as an admin:

```bash
bench --site <site> execute benchpress.waitlist.notify_of_signup
```

It emails every entry that has not been mailed about the retirement — approved entries get the
login page, everyone else gets signup — and stamps `Invite Sent On` on the row. Running it again
mails nobody twice, so it is safe to re-run if a batch stops half way.

---

## Turning it back off

Set **Waitlist Open** back on. Signup refuses, Disable Signup goes back on, and the landing page
shows the form again. Accounts already created keep their role, their balance and their instances.
