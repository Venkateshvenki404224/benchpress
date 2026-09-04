`<reasoning_effort>40</reasoning_effort>`

# security_and_credentials

Three endpoints in this app decrypt a stored password and hand it to a browser, and the screens
that show them are documented as plain-text by design. Every other guard in the codebase exists to
make sure the caller asking for one is entitled to it: 53 of 55 whitelisted methods check
permissions in their first lines, and the two that do not are document methods where Frappe checks
first. A guard removed here does not fail loudly — it just serves somebody else's credentials.

The test before writing an endpoint, a filter or a template: **who is the caller, and what stops
them asking for a row that is not theirs?**

```
+---------------------------------------------------------------------------+
|  A DECRYPTED PASSWORD IS NEVER LOGGED, NEVER CACHED, NEVER PUT IN A URL,   |
|  AND NEVER RETURNED TO A CALLER THAT HAS NOT PASSED REQUIRE_BENCH_ACCESS.  |
|  THE THREE FIELDS ARE SSH_PASSWORD, ADMIN_PASSWORD, CODE_SERVER_PASSWORD.  |
+---------------------------------------------------------------------------+
```

## credentials

- `get_bench_credentials` (`api.py:729`) and `get_code_server_credentials` (`api.py:715`) both open
  with `require_bench_access(bench_name)` before decrypting anything — Benchpress keeps that call as
  the first statement, because a check after a read has already done the read.
- A stored password is read with `frappe.utils.password.get_decrypted_password`, never from a
  plain field, since the encrypted store is the only place these values legitimately live.
- A decrypted value is returned and dropped. It is never passed to `frappe.log_error`, never put
  in a `frappe.throw` message, and never written to a Deploy Log line.
- `benchpress/config/.env.example` is the only credential-shaped file tracked, and it holds
  placeholders. A real value that reaches this repo is rotated first and stripped second —
  stripping alone leaves it in the history and in every clone.
- Benchpress reports the location of a leaked secret as `path:line` and never reproduces the value,
  because a report that quotes a key spreads it into logs and chat.
- SQL sent to a bench database is piped in base64 (`mariadb_manager.execute_sql`) so nothing is
  shell-interpolated, and it leaves no temp file behind on the failure path.
- A generated password uses `secrets`, not `random` — `mariadb_manager._random_string` calls
  `secrets.token_urlsafe`, because `random` is seeded predictably and is not a security primitive.

## permission_guards

- Every module-level `@frappe.whitelist()` checks for itself — `require_admin()`,
  `require_app_user()` or `require_bench_access()` from `benchpress/permissions.py` — because
  Frappe applies no doctype check to a plain function.
- A tenant-scoped doctype needs **both** halves of its rule: a `permission_query_conditions` entry
  and a `has_permission` entry, registered together at `hooks.py:142` and `hooks.py:152`. Query
  conditions reach only the list engine, so a doc read past one is unguarded.
- Benchpress reuses `get_bench_owner_filter()` rather than writing `{"owner": frappe.session.user}`
  inline — ownership, not the role, decides which benches a person sees, and one function owns it.
- A guest endpoint is `allow_guest=True` **and** `methods=["POST"]` **and** rate-limited. All three
  of them are — `benchpress/contact.py:45`, `benchpress/waitlist.py:26` and
  `benchpress/signup.py:20`.
- `@public_form(limit)` from `benchpress/throttle.py` spends two counters per call — one per
  address and email, one per address alone at `PER_ADDRESS_HOURLY = 10` — since a per-email limit
  alone is defeated by changing the email.
- The whole public site is gated by `benchpress.public_site.require_public_site`, which raises
  `PageDoesNotExistError` while `benchpress_public_site` is unset. A self-hoster gets no
  marketing pages, and Benchpress does not add a route that escapes that gate.

## output_escaping

- Jinja autoescape is off in Frappe, so every template escapes by hand — there are 429 `| e`
  filters across `benchpress/www/` and `benchpress/templates/`, and a new value gets one.
- A value rendered raw carries a comment saying what it is, as at `www/services.html:43-44`:
  shipped HTML from a Python seed, a macro's output, or a framework helper's. Benchpress writes that
  comment or adds `| e`; there is no third option.
- Guest-typed text reaches a mail template only through `benchpress/emails.py`, which wraps it in
  `Markup` on the way — that is the one path, and Benchpress does not open another.
- The SPA has zero `v-html` and zero `innerHTML` uses. Benchpress keeps both at zero, because Vue's
  default interpolation already escapes and an exception here is an XSS sink by definition.

## client_side_state

- `localStorage` in this app holds one thing: the light/dark mode in `bp-site.bundle.js:23`. No
  token, no session, no credential goes into browser storage, since anything there is readable by
  every script on the origin.
- Both the read and the write are wrapped in `try`/`catch` (`bp-site.bundle.js:21-26, 52-58`)
  because a browser in private mode throws, and an unguarded write blanks the page.
- Requests from the public pages send `credentials: "same-origin"` and a CSRF header taken from
  `data-csrf-token` on the body — the marketing templates emit no boot payload, so the token has
  no other source.
- Benchpress does not log a response or an error object wholesale; the 36 `frappe.log_error` sites
  pass a title and either a traceback or a formatted string, never a raw payload.

## what_not_to_do

- Do not write a module-level `@frappe.whitelist()` without a permission call in its first lines.
- Do not register `permission_query_conditions` for a doctype without its `has_permission` twin.
- Do not log, echo, or embed a decrypted password, an API secret, or a MariaDB root password.
- Do not add `allow_guest=True` without both a POST-only method list and a `@public_form` limit.
- Do not render a template value without `| e` unless a comment beside it says what makes it safe.
- Do not introduce `v-html`, `innerHTML`, or a `| safe` filter — all three are at zero today.
- Do not put anything in `localStorage` beyond a display preference.
