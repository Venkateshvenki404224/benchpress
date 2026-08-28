---
title: Start, stop and redeploy
description: The five actions on a running bench, which of them destroy work,
  and which are admin-only.
lastModified: "2026-08-28T10:10:48Z"
lastAuthor: Venkatesh
---
# Start, stop and redeploy

A running bench has five actions. Two are safe, one is destructive, one is
final, and one is admin-only. This page says which is which before you press
anything.

**Who this is for.** Anybody with a deployed bench.

**Before you start.** The bench must have been deployed at least once. An
action on a bench that has no container is refused with
`This instance has no container — deploy it first.`

## Steps

1. Open the lab. The primary button on the right is the next step in the
   bench's own lifecycle, and it changes as the bench changes.

   |Bench state|Primary button|What it does|
   |--|--|--|
   |Never deployed|**Deploy**|Runs the eleven-step pipeline|
   |`Deploying`|**Deploying…**, disabled|Reports work already running|
   |`Running`|**Open site**|Opens the site over the VPN|
   |`Stopped`|**Start**|Resumes the same container|
   |Lab is `Error`|**Rebuild image**|Builds the image again. Admins only|

   **Start** is the primary action on a stopped bench, never **Redeploy**. The
   container's writable layer holds everything done inside the bench, so the
   destructive path is never the default.

   ![The BenchPress lab page for Helpdesk sandbox as a non-admin user, at 1280 by 800 pixels. The Container card reads Running in green, Health Healthy checked 1m ago, CPU 0 percent of quota 2 vCPU, MEMORY 3 percent of a 2 GB limit, and Started 2 minutes ago. The overflow menu beside Open site is open and offers exactly two items, Stop bench and Redeploy bench. The Sites card lists the site with seven app chips: Frappe, ERPNext, HR, CRM, Telephony, Helpdesk, Payments and Learning.](../images/user/lifecycle/01-actions-menu.png)

2. Press the **…** button beside the primary action for the rest. The menu
   holds what the primary button is not offering.

   |Menu item|Effect|Who sees it|
   |--|--|--|
   |**Stop bench**|Stops the container. Keeps the database|Everybody|
   |**Redeploy bench**|Replaces the container and the site|Everybody|
   |**Rebuild image**|Builds the lab image again|Admins|
   |**Delete bench**|Removes the container, the sites and the databases|Admins|

   In the frame above, a BenchPress User sees two items. An admin sees four.

3. Confirm. Every action in the menu asks first, and the dialog names what it
   does.

   ![A confirmation dialog over the Helpdesk sandbox lab page, at 1280 by 800 pixels. The dialog is headed Stop this bench? and reads, The container stops and the site goes offline until it is started again. Nothing is deleted. A single black Confirm button sits below the text, with a close cross at the top right.](../images/user/lifecycle/02-stop-confirm.png)

   Read the second sentence. It is where the dialog says whether anything is
   lost. **Stop** says `Nothing is deleted`. **Redeploy** does not.

4. Watch the page settle. A stop takes a few seconds.

   ![The Helpdesk sandbox lab page after the stop, at 1280 by 800 pixels. The Container card header now reads Stopped in gray, while Health still reads Healthy with the note checked 2m ago. CPU and MEMORY both read a dash and container not running. The card ends with Started 3 minutes ago and Can be restored for 6d 23h. The primary button has become Start. The Sites card marks the site Inactive and Not running, with the line This site's container is stopped. Deploy the lab to bring it back.](../images/user/lifecycle/03-stopped.png)

   Two things in that frame are worth naming. Health still reads `Healthy`,
   because the last probe ran before the stop. And a countdown has appeared:
   `Can be restored for 6d 23h`.

5. Press **Start** to bring it back. The same container resumes with everything
   in it. Nothing is rebuilt and nothing is downloaded.

## Verify

* After **Stop**, the Container card reads `Stopped` and the primary button
  reads **Start**.
* After **Stop**, the site row reads `Inactive` and `Not running`.
* After **Start**, the Container card reads `Running` within a few seconds.
* After **Redeploy**, the deploy log shows a new run with all eleven steps.

## Troubleshooting

|Symptom|Cause|Fix|
|--|--|--|
|`This instance has no container — deploy it first`|The bench was never deployed, or it was reaped|Press **Deploy**|
|**Delete bench** is missing from the menu|Deleting is admin-only|Ask an admin|
|**Rebuild image** is missing from the menu|Rebuilding is admin-only|Ask an admin|
|**Start** is refused|A concurrency cap or a credit hold applies to the start|Stop another bench, or ask the operator|
|The stopped bench disappeared|A stopped bench is deleted after `reap_after_days`|Deploy it again. The container is gone|
|Files written inside the bench are missing after a redeploy|Redeploy replaces the container and its writable layer|Keep work in git, not only in the container|
|SSH or code-server passwords stopped working|They are regenerated on every redeploy|Reopen **Connection details** and copy them again|

## Reference

### What each action keeps

|Action|Container|Writable layer|Site database|WireGuard peer|
|--|--|--|--|--|
|**Stop**|kept, not running|kept|kept|kept|
|**Start**|resumed|kept|kept|kept|
|**Redeploy**|replaced|**lost**|replaced|reassigned|
|**Delete**|removed|**lost**|**dropped**|removed|
|**Rebuild image**|untouched until the next deploy|untouched|untouched|untouched|

**Redeploy is not a restart.** It throws the container away and makes a new one
from the lab image. Use **Start** when the bench is only stopped.

### Who may do what

|Action|BenchPress User|BenchPress Admin|
|--|--|--|
|Deploy|yes|yes|
|Start|yes|yes|
|Stop|yes|yes|
|Redeploy|yes|yes|
|Rebuild image|no|yes|
|Delete|no|yes|

A user sees only their own benches. An admin sees every bench on the server.

### Stopping is the answer to a refused start

A start passes the same admission gate a deploy does. Stopping and deleting do
not, because stopping is what a refused caller is being told to do.

### After a stop, the countdown

|Setting|Where|Value here|
|--|--|--|
|`reap_after_days`|Credit Settings|7 days|

A stopped bench past that window is torn down. An email goes out two days
before, so nothing disappears without notice. `0` turns the deletion off.

## Related

* [Read a lab page](/docs/user/lab-detail) — the fields these actions change.
* [Deploy from a template](/docs/user/deploy-from-template) — the eleven steps a redeploy runs again.
* [Create a lab](/docs/user/create-a-lab) — what a rebuild rebuilds.
