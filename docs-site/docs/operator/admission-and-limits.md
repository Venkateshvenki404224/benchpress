---
title: Admission and limits
description: Optional and off by default — concurrency caps, size ceilings,
  device and build quotas, how a slot is claimed as a row, and the acceptance
  run that proves access still works.
lastModified: "2026-08-28T13:08:38Z"
lastAuthor: Venkatesh
---
# Admission and limits

**Optional, and off by default.** The caps on this page only bind while
`enable_credits` is `1`, except the device cap and the build cap, which bind
whenever the setting holds a number.

**Who this is for.** Somebody running BenchPress for a team, who needs one
person's benches not to fill the host.

**Before you start.** This describes running BenchPress **for other people**.
None of it is required to deploy a bench on your own machine. Read
[Credits and billing](/docs/operator/credits-and-billing) first — it owns the
switch that most of this hangs off.

## The caps

|Cap|Setting|On this host|Binds when|
|--|--|--:|--|
|Concurrent instances, never purchased|`max_concurrent_free`|2|credits on|
|Concurrent instances, has purchased|`max_concurrent_paid`|5|credits on|
|Concurrent instances, credits off|`max_concurrent_uncredited`|0 = unlimited|credits **off**|
|Largest size on a free account|`max_size_free`|empty = no ceiling|credits on|
|Sites per instance|`Instance Size.max_sites`|3 / 5 / 10|always|
|VPN devices per account|`max_devices`|5|always|
|Custom image builds per day|`max_builds_per_day`|3|always|

**`max_concurrent_uncredited` reads backwards from how most people expect.**
It applies only while credits are **off**, and `0` there means unlimited, not
zero. Switching credits on does not engage it. The cap becomes
`max_concurrent_free`, or `max_concurrent_paid` once the account holds any
`Purchase` ledger row.

The switch from free to paid reads the row rather than the balance, because a
refund clears the balance and the account has still plainly paid.

## Steps

1. Open `/app/credit-settings` in Desk.

   ![The Credit Settings document in Frappe Desk, Free but Capped section. Max Concurrent (Free) is 2, Max Concurrent (Paid) is 5, Max Concurrent (Credits Off) is 0, Max Devices is 5, Max Builds per Day is 3, and Max Size (Free) is empty. Every field's help text ends with the same sentence: 0 equals unlimited.](../images/operator/admission-and-limits/01-credit-settings-caps.png)

   The **Free but Capped** section holds five of the seven caps:
   `max_concurrent_free` 2, `max_concurrent_paid` 5,
   `max_concurrent_uncredited` 0, `max_devices` 5 and `max_builds_per_day` 3.
   `max_size_free` is empty.

2. Set the per-size limits at `/app/instance-size`. Three sizes ship:

   |Size|Memory|CPU|Max sites|Credits per hour|Price multiplier|
   |--|--|--:|--:|--:|--:|
   |Small (default)|1g|1|3|1|1.0|
   |Medium|2g|2|5|2|1.0|
   |Large|4g|4|10|4|1.0|

   Every size ships with `include_code_server` on and with `disk_limit`,
   `pids_limit`, `iops_limit` and `bps_limit` at `0`, which means unset.

3. Save. Caps are read per request, so a change binds on the next call. There
   is nothing to restart.

## Verify

Ask the app what one user's ceiling is, rather than reading the settings:

```bash
bench --site <site> execute benchpress.credits.guard.concurrency_limit \
  --kwargs "{'user':'someone@example.com'}"
```

`0` means unlimited. Any other number is what that account may hold at once.

## How a slot is actually taken

This is the part that surprises people reading the code, and it explains the
refusal messages.

Counting running instances and comparing cannot refuse anything. Two requests
that arrive together read the same count and both pass. A new bench row is
written as `Draft` for the two minutes a deploy takes, so an in-flight deploy
is invisible to anything counting deploys.

So **a slot is a row**, not a count. `Bench Admission` is named after the
bench, which puts the claim on a primary key, and every read and write happens
under a row lock on the caller's `Credit Account`. The loser of a race waits
there and then reads what the winner wrote.

Three consequences an operator will meet:

* **A hold is not a charge.** It moves no balance and writes no ledger row.
  The charge happens when the bench reaches `Running`, in the same locked
  transaction that ends the hold. A user who reads their statement during a
  deploy sees nothing yet, and their spendable balance is still lower.
* **A redeploy, a restart and a retry are free of the cap.** The bench already
  holds its slot, so the claim returns without refusing. The cap forbids new
  instances, not touching existing ones.
* **A slot can leak** if a worker is killed between the claim and the charge.
  `benchpress.credits.admission_repair.reconcile_admissions` runs every five
  minutes precisely because a leaked slot is a lockout for somebody at their
  cap.

## The refusals, and what each one means

Every cap refuses by name. These are the messages a user will quote at you.

|Message|Cap|What to do|
|--|--|--|
|`You have N instances running, the most your plan allows`|concurrency|They stop one, or buy credits to move to the paid cap|
|`The <size> size is not available on a free account`|`max_size_free`|They deploy smaller, or buy credits|
|`This instance already has the N sites its size allows`|`Instance Size.max_sites`|They redeploy the lab at a larger size|
|`You already have N devices, the most allowed`|`max_devices`|They remove a machine they no longer use|
|`You have used today's N custom image builds`|`max_builds_per_day`|They wait, or deploy a lab whose recipe is already built|
|`Not enough credits: this needs X and Y are available`|balance|They pick a shorter plan, or buy credits|
|`This account is suspended, so nothing new can be started`|`is_suspended`|An operator clears the flag|

The build cap counts against the **lab's owner**, not the caller, because that
is the account the build's ledger row is written to. It rides only on the
explicit build action. A build that the deploy path performs is a cache miss
the user did not ask for, and the credit charge is the control there.

## The acceptance run

Repeat this after any change to the deploy pipeline, the lab image, or the
access surface. It answers one question: **can a user reach the lab they were
just told is ready?**

Run it against a lab deployed from a template, from a machine with the tunnel
up. Record the result of every step. A step that was not exercised is reported
as not exercised, never as a pass.

Throughout, `<wg_ip>` is the bench's WireGuard address, `<user>` its SSH
username and `<site>` its site name. All three are on the **Connection
details** card.

1. **The deploy is genuinely green.** All eleven steps read `success` in the
   stepper, and the raw log holds no `[warn]` line. A build that ran inside
   the deploy has its own tab, and a warning there is a real finding even when
   the deploy is green.

2. **The site loads and the admin password works.**

   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' http://<wg_ip>:8000/
   curl -s -X POST http://<wg_ip>:8000/api/method/login -d "usr=Administrator&pwd=<admin_password>"
   ```

   Expect `200` and `{"message":"Logged In"}`.

3. **The IDE opens, with its password in hand.** **Open VS Code** opens
   `http://<wg_ip>:8080/` and a password dialog appears on the lab page. The
   password is never in the URL — a query parameter would land in browser
   history, in the container's access log, and in every proxy between.

   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' http://<wg_ip>:8080/       # 302
   ```

4. **The integrated terminal is a real bench shell.** Inside code-server:

   ```bash
   whoami                                # the lab's ssh username, not frappe
   pwd                                   # /home/<user>/frappe-bench
   bench --site <site> list-apps
   bench version
   ```

   All four must work with no `sudo` and no PATH fix.

5. **SSH does the same from your own machine.**

   ```bash
   ssh <user>@<wg_ip>
   ```

   **A one-shot command is not a login shell.** Debian's `.bashrc` returns
   early for non-interactive shells, before the bench block, so
   `ssh <user>@<wg_ip> "bench --site <site> list-apps"` starts in the home
   directory and reports *Command not being executed in bench directory*. Name
   the directory when scripting:

   ```bash
   ssh <user>@<wg_ip> "cd frappe-bench && bench --site <site> list-apps"
   ```

6. **Off the tunnel, the UI is honest.** Disconnect and return to the browser
   tab without reloading. **Open site** and **Open VS Code** are disabled and
   say why. Each site row reads `Unreachable` with its own reason, distinct
   from a stopped container's. Reconnecting re-enables them on the next focus
   of the tab. Nothing spins forever.

7. **With the bench stopped, nothing offers a dead address.** **Open VS Code**
   is gone, the site row reads `Inactive` with its Open button disabled, and
   the primary action is **Deploy**.

8. **A failed deploy names its own cause.** Point a Lab App row at a branch
   that does not exist and deploy. The banner names the **image build**
   failure, not the deploy's log tail, and its button opens the **Build log**
   tab.

Two known intermittents, neither a defect of the step they break.
`wg-quick up wg0` can report *wg0 already exists* at step 5 when the
container's entrypoint won the race — retry the deploy. `codeload.github.com`
rate-limits in bursts, and a 429 during an image build is retryable.

## Troubleshooting

|Symptom|Cause|Fix|
|--|--|--|
|A user is refused at a cap they are not at|A slot leaked from a killed worker|Wait for `reconcile_admissions`, or run it by hand|
|Raising a cap changed nothing|The account is refused on balance, not concurrency|Read the exact message. They name different numbers|
|`max_concurrent_uncredited` seems to do nothing|Credits are on, and it only applies while they are off|Change `max_concurrent_free` instead|
|A user cannot add a device on a fresh install|`max_devices` binds even with credits off|Raise it, or have them remove one|
|Every build is refused after three|`max_builds_per_day` counts against the lab owner|Wait for tomorrow, or deploy a lab already built|
|The size picker hides sizes|`max_size_free` is set and the account has never purchased|Clear the ceiling, or let them buy credits|

## Reference

|Setting|Value here|Scope|
|--|--:|--|
|`max_concurrent_free`|2|credits on, never purchased|
|`max_concurrent_paid`|5|credits on, has purchased|
|`max_concurrent_uncredited`|0 (unlimited)|credits off|
|`max_size_free`|empty|credits on|
|`max_devices`|5|always|
|`max_builds_per_day`|3|always|
|`Instance Size.max_sites`|3 / 5 / 10|always|

|Job|Schedule|Purpose|
|--|--|--|
|`benchpress.credits.admission_repair.reconcile_admissions`|every 5 minutes|free slots leaked by a killed worker|
|`benchpress.credits.sweep.enforce_limits`|every 5 minutes|check balances, never the clock|

Lock order across the app is fixed: `Bench Instance`, then `Credit Account`,
then `Bench Admission`. Nothing in admission locks an instance, so admission
cannot close that cycle.

## Related

* [Credits and billing](/docs/operator/credits-and-billing) — the switch these caps hang off.
* [Users and roles](/docs/operator/users-and-roles) — who is exempt from what.
* [Troubleshooting](/docs/user/troubleshooting) — the same refusals, indexed for the user who hit one.
