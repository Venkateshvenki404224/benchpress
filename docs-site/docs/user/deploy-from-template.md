---
title: Deploy from a template
description: Turn a catalog template into a running bench, and read the eleven
  pipeline steps while they run.
lastModified: "2026-08-30T20:13:11+05:30"
lastAuthor: Venkatesh
---
# Deploy from a template

A template is a recipe someone already wrote. This page takes you from the
catalog to a bench you can open, without filling in a form.

**Who this is for.** Anybody who needs a working bench and does not care how the
image was built.

**Before you start.** You need a login. **Templates** is admin-only, so ask an
admin if the item is missing from your sidebar. You do not need the VPN to
deploy. You need it to open the bench afterwards.

## Steps

1. Open **Templates** in the sidebar, or go to `/frontend/labs/templates`.

   ![The BenchPress Templates catalog at 1280 by 800 pixels, showing eight template cards in a three-column grid. Each card carries a logo, a title, a Frappe version, a description, app chips and resource chips. VPN Management and ERPNext are tagged Most used. The first four cards read Already used and offer a Go to lab button. Google, ChatGPT, Claude and BenchPress read a deploy estimate such as 12 min to deploy and offer a Use template button instead.](../images/user/deploy-from-template/01-templates.png)

   Every card names the same five things: the app list, the Frappe version, the
   memory and CPU the bench gets, and either a deploy estimate or the lab that
   already exists.

   |Template in the frame|Version|Size|Estimate|
   |--|--|--|--|
   |VPN Management|version-16|1 GB, 1 vCPU|already used|
   |ERPNext|version-15|2 GB, 2 vCPU|already used|
   |Frappe CRM|version-15|1 GB, 1 vCPU|already used|
   |Frappe|version-16|4 GB, 4 vCPU|already used|
   |Google|version-16|2 GB, 2 vCPU|\~12 min|
   |ChatGPT|version-16|2 GB, 2 vCPU|\~12 min|
   |Claude|version-16|4 GB, 4 vCPU|\~20 min|
   |BenchPress|version-16|2 GB, 2 vCPU|\~8 min|

   Use the three controls above the grid to narrow it: a search box, an **Apps**
   filter and a **Version** filter.

2. Press the button on the card you want. The button tells you which of two
   things happens.

   |Button|What the card says|What the press does|
   |--|--|--|
   |**Use template**|a deploy estimate|Creates the lab, then starts the deploy|
   |**Go to lab**|`Already used — ready`|Opens the lab that already exists|

   **Use template** is one press for two actions. BenchPress creates a lab from
   the recipe, then deploys a bench from that lab. The estimate on the card is
   the build time, and it applies only the first time a template is used.

3. Press **Deploy** on the lab page. A lab that has already been used still
   needs this press, because a lab is a recipe and a bench is a container.

4. Watch the eleven steps. Open the **Deploy log** tab to see them.

   ![An animation of the BenchPress Deploy log tab during a real deploy of the crm-demo lab. The header reads Latest deploy, Deploying, and a counter that climbs from 2 seconds to 1 minute 25 seconds. The eleven steps tick over one at a time from Checking shared infrastructure to Deploy complete, each gaining a check mark, a one-line result and its own duration. The header ends on a green Success chip.](../images/user/deploy-from-template/04-pipeline.gif)

   The steps run in this order every time. The order is the order the code
   runs, which is why the WireGuard peer comes fifth and not tenth.

   |#|Step|What it does|
   |--|--|--|
   |1|Checking shared infrastructure|Confirms MariaDB and the Docker network answer|
   |2|Preparing the lab image|Finds the lab's built image. A deploy never builds one|
   |3|Creating the container|Starts the container on the bench bridge|
   |4|Waiting for the container IP|Waits for an address, and for TLS on the wildcard certificate|
   |5|Configuring the WireGuard peer|Gives the bench its private VPN address|
   |6|Writing common\_site\_config.json|Points the bench at the shared database and Redis|
   |7|Creating the site|Restores the site, or builds it from scratch|
   |8|Preparing assets|Uses the assets already bundled into the image|
   |9|Provisioning the SSH user|Creates the SSH account and its password|
   |10|Starting the lab's services|Starts code-server and reports its address|
   |11|Deploy complete|Marks the bench Running|

   ![The Deploy log tab of the crm-demo lab part way through a run, at 1280 by 800 pixels. The header reads Latest deploy, a blue Deploying chip and 4s so far. The first six steps carry green check marks and durations of one second or less. Creating the site is bold with a spinner and a blue running label, and reports the site name it is creating. Preparing assets, Provisioning the SSH user, Starting the lab's services and Deploy complete are still gray.](../images/user/deploy-from-template/02-pipeline.png)

   Each step keeps its own clock, and each reports one line of its own result.
   In the frame above, six steps are done, `Creating the site` is running, and
   four have not started.

5. Wait for **Success**. The header chip turns green and reports the total.

   ![The same Deploy log tab after the run finished, at 1280 by 800 pixels. The header reads Latest deploy with a green Success chip and 21s. All eleven steps carry check marks. Creating the site took 15 seconds and reports that the site was restored from the image's golden dump. The page header now offers Open VS Code and Open site instead of a Deploy button.](../images/user/deploy-from-template/03-complete.png)

   This run took **21 seconds**, and 15 of those were step 7. The step-by-step
   times were 1s, 1s, 1s, 0s, 1s, 0s, 15s, 0s, 1s, 1s.

   A deploy is that fast only when the image carries a golden dump. Step 7 then
   reports `restored from the image's golden dump`. Without one it reports
   `built from scratch`, and the same step takes minutes rather than seconds.
   Step 2 says so in the log when the dump is missing.

## Verify

The deploy worked when all four are true.

* The **Deploy log** header reads **Success** and names a duration.
* All eleven steps carry a check mark.
* The page header offers **Open site** and **Open VS Code** in place of **Deploy**.
* The **Sites** card lists one site and marks it **Active**.

## Troubleshooting

|Symptom|Cause|Fix|
|--|--|--|
|**Templates** is missing from the sidebar|The catalog is admin-only|Ask an admin, or deploy an existing lab from **Labs**|
|Step 2 fails with `No built image for lab`|The lab has no image, or its recipe changed after the last build|Ask an admin to press **Rebuild image** on the lab|
|The log stops at `Waiting for the worker to pick the deploy up…`|No worker is running, so nothing has started|Ask the operator to check `queue-long`|
|Step 7 runs for minutes|The image has no golden dump, so the site is built from scratch|Nothing to fix. Read step 2, which reports the same thing|
|The run ends **Error**|The step that failed names the reason|Open **Raw log** under the steps and read the last lines|
|**Open site** opens nothing|The site has no public name, so it answers only on the VPN|Connect the VPN, then press it again|

## Reference

### The two buttons on a template card

|State|Footnote|Button|
|--|--|--|
|No lab exists yet|`~N min to deploy`|**Use template**|
|A lab exists|`Already used — <status>`|**Go to lab**|

### What a template sets

|Field|Example in the catalog|
|--|--|
|Apps|`crm` on branch `main`|
|Frappe version|`version-15`|
|Instance size|Small, Medium or Large|
|Memory and CPU|1 GB and 1 vCPU for Small|
|Deploy estimate|4 to 20 minutes, first build only|

### The three tabs a deploy fills

|Tab|What it holds|
|--|--|
|Dashboard|Container status, health, CPU, memory and connection details|
|Sites|Every site on the bench, and whether each is active|
|Deploy log|The eleven steps, their durations and the raw log|

## Related

* [Quick tour](/docs/user/quick-tour) — the five screens, and what each one owns.
* [Create a lab](/docs/user/create-a-lab) — when no template fits.
* [Read a lab page](/docs/user/lab-detail) — what every field on the page means.
* [Start, stop and redeploy](/docs/user/lifecycle) — what to do after it is running.
