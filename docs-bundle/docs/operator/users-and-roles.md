---
title: Users and roles
description: The two BenchPress roles, what each one may read and write, which
  screens are admin-only, and how ownership rather than a role decides who sees
  a bench.
lastModified: "2026-08-28T13:08:38Z"
lastAuthor: Venkatesh
---
# Users and roles

Two roles, and one rule that matters more than either: a user sees their own
benches, and an admin sees everybody's.

**Who this is for.** Whoever grants access.

**Before you start.** BenchPress adds two roles. It does not replace Frappe's
permission model — `System Manager` still holds everything, and every check
below is a normal Frappe permission.

## The two roles

|Role|Desk access|Who it is for|
|--|--|--|
|`BenchPress User`|no|Somebody handed a login who deploys and uses benches|
|`BenchPress Admin`|yes|Somebody who curates labs and templates, and can see every bench|

`System Manager` is treated as an admin everywhere BenchPress checks, so a
site administrator needs no extra role.

On this host: 35 users, 21 with `BenchPress User`, 2 with `BenchPress Admin`
and 6 with `System Manager`.

## Steps

1. Open `/app/user` in Desk **as a System Manager** and pick the person, then
   open the **Roles & Permissions** tab.

   ![The Frappe Desk User document for Sam Intern, intern@benchpress.cloud, on the Roles and Permissions tab. The role checklist shows BenchPress User ticked, with BenchPress Admin, System Manager and every other role unticked. The sidebar is Frappe's Users workspace and the footer reads Administrator.](../images/operator/users-and-roles/01-user-roles.png)

   **A `BenchPress Admin` cannot do this.** That role grants no access to the
   `User` doctype, so `/app/user` answers `User <email> does not have doctype access via role permission for document User`. Granting roles is a
   `System Manager` action, and it is the one administrative task the
   BenchPress admin role does not cover.

2. Add exactly one BenchPress role in the **Roles** section. `BenchPress User`
   for somebody who will use benches. `BenchPress Admin` for somebody who will
   curate them.

3. Save. Roles are read per request, so the change binds on their next call.

Self-serve signup assigns `BenchPress User` automatically. See
[Self-serve signup](/docs/operator/hosted-signup).

## Verify

Read the roles back from the server rather than from the form you just saved.

```bash
bench --site <site> execute frappe.client.get_list \
  --kwargs "{'doctype':'Has Role','filters':{'parent':'someone@example.com'},'fields':['role'],'limit_page_length':0}"
```

Then confirm what the person will actually see. `benchpress.api.get_user_context`
returns the caller's identity and roles, and the SPA renders the sidebar from
it. The user-facing proof is simpler still: **Templates** is in the sidebar
for an admin and absent for a user, and the **New lab** button in the Overview
header appears only for an admin.

## What each role may do

Read as: `r` read, `w` write, `c` create, `d` delete. **Own** means the
permission is limited to documents the user owns.

|DocType|System Manager|BenchPress Admin|BenchPress User|
|--|--|--|--|
|`Lab`|r w c d|r w c d|r|
|`Bench Instance`|r w c d|r w c d|r w c — **own**|
|`Bench Site`|r w c d|r w c d|r w — **own**|
|`Lab Template`|r w c d|r w c d|r|
|`Build Log`|r w c d|r w c d|r|
|`Deploy Log`|r w c d|r w c d|r|
|`Database Server`|r w c d|r w c d|—|
|`BenchPress Settings`|r w c d|r w c d|—|
|`Credit Settings`|r w c d|r w c d|—|
|`Credit Account`|r w c d|r w|—|
|`Credit Ledger Entry`|r c d|r|—|
|`Credit Pack`|r w c d|r w c d|r|
|`Lease Plan`|r w c d|r w c d|r|
|`Instance Size`|r w c d|r w c d|r|
|`Waitlist Entry`|r w c d|r w c d|—|

Three of those rows deserve a sentence.

* **A `BenchPress User` reads every Lab.** `Lab` read is not limited to the
  owner, on purpose — a lab is a shared catalog entry. What they cannot see is
  other people's **benches**.
* **`Credit Ledger Entry` is not writable by anybody**, not even a System
  Manager. Entries are appended by the accounting code and never edited, which
  is what makes a balance auditable.
* **`Credit Account` has no `BenchPress User` row at all.** Users read their
  own balance through the API, which applies its own owner check, not through
  the DocType.

## Ownership, not the role, decides who sees a bench

A user's list is filtered by ownership at the query level, not by hiding rows
in the UI. Six doctypes carry a query condition and a per-document check:
`Bench Instance`, `Credit Account`, `Credit Ledger Entry`, `Deploy Log`,
`Bench Event` and `Build Log`.

Two facts follow that people get wrong:

* **Two users deploying the same lab get two different benches.** The bench id
  is `md5(email + lab)`, so each user's deploy is their own instance from the
  same lab. Neither sees the other's.
* **An admin sees everybody's benches**, because the owner filter returns
  empty for an admin rather than being skipped in the template.

## The admin-only surfaces

Confirmed by looking at both roles in the running app:

|Surface|Why it is admin-only|
|--|--|
|**Templates** in the sidebar|curating the catalog|
|**New lab** in the Overview and Labs header|creating a lab is a write on `Lab`|
|**Settings** in the account menu|`BenchPress Settings` is not readable by a user|
|The **Build log** tab on a lab|build output can name private repositories|
|**Rebuild image** in the overflow menu|it costs an image build|
|**Delete bench** in the overflow menu|delete is admin-gated even for the bench's owner|

A `BenchPress User` gets exactly two items in the bench overflow menu: **Stop**
and **Redeploy**.

## How the checks are written

Every whitelisted endpoint checks for itself. There is no blanket decorator
that would let a new endpoint ship unguarded by omission.

|Guard|Meaning|
|--|--|
|`require_admin()`|`System Manager` or `BenchPress Admin`, or it raises|
|`require_app_user()`|any of the three roles, or it raises|
|`require_bench_access(name)`|a real Frappe read permission on that bench document|
|owner filter|`{"owner": session.user}` for a user, `{}` for an admin|

## Troubleshooting

|Symptom|Cause|Fix|
|--|--|--|
|The app refuses at login with no roles|The user has none of the three roles|Add `BenchPress User`|
|A user cannot see a bench a colleague described|They see only their own benches|Have the owner share, or use an admin account|
|A user sees a lab but has no **Deploy**|Deploy writes a `Bench Instance` they will own. Check the caps instead|See [Admission and limits](/docs/operator/admission-and-limits)|
|An admin cannot open Settings|They hold `BenchPress User` only|Change the role, then have them reload|
|A `BenchPress Admin` cannot open `/app/user`|The role grants no `User` doctype access|Grant roles as a `System Manager`|
|A user can reach Desk|They hold a role with desk access, such as `BenchPress Admin`|Give them `BenchPress User` instead|
|Deleting a bench is refused for its owner|Delete is admin-only by design|An admin deletes it|
|A new signup has no credits|The grant posts once per address, ever|See [Self-serve signup](/docs/operator/hosted-signup)|

## Reference

|Item|Value|
|--|--|
|Admin roles|`System Manager`, `BenchPress Admin`|
|App roles|`System Manager`, `BenchPress Admin`, `BenchPress User`|
|Role needed to grant a role|`System Manager`|
|Bench id|`md5(email + lab)`|
|Owner filter|`{"owner": session.user}`, empty for an admin|
|Role assigned at signup|`BenchPress User`|
|Desk access|`BenchPress Admin` yes, `BenchPress User` no|

## Related

* [Self-serve signup](/docs/operator/hosted-signup) — where the user role comes from on a hosted install.
* [Admission and limits](/docs/operator/admission-and-limits) — what a role does not decide.
* [Quick tour](/docs/user/quick-tour) — the sidebar as a user sees it.
