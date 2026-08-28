---
title: Troubleshooting
description: Every symptom a BenchPress user meets, its cause, and the page that
  fixes it — deploys, the VPN, SSH, code-server, logs and credits.
lastModified: "2026-08-28T11:17:35Z"
lastAuthor: Venkatesh
---
# Troubleshooting

One index of symptoms across the whole app. Find the line that matches what
you see, then read the cause and the fix.

**Who this is for.** Anybody whose bench is not doing what they expected.

**Before you start.** Read the message on screen first. BenchPress refuses by
name: every refusal states the number that was hit or the thing that is
missing, and most of them name the fix. This page is for the cases where the
message is not enough.

## Start here

Three readings answer most questions, and they are all on the lab page.

|Reading|Where|Says|
|--|--|--|
|Container status|Container card header|whether the bench is running|
|Health|Container card, beside the status|whether the site answered the last probe|
|VPN chip|page header, top right|whether **your machine** is on the tunnel|

Check them in that order. A stopped container and a down tunnel look the same
from a browser and have nothing to do with each other.

## Nothing loads

|Symptom|Cause|Fix|
|--|--|--|
|`/frontend` sends you to `/login`|No session|Sign in, then open `/frontend` again|
|The sidebar has no **Templates**, **New lab** or **Settings**|Those screens are admin-only|Ask an admin. See [Quick tour](/docs/user/quick-tour)|
|The sidebar has no credit meter and `/frontend/credits` bounces to Labs|Credits are switched off on this server|Nothing to do. See [Leases and credits](/docs/user/leases-and-credits)|
|A lab you were shown is not in your list|A user sees only their own benches|Ask the owner, or an admin|

## The deploy

|Symptom|Cause|Fix|
|--|--|--|
|**Deploy** is missing and the button reads **Deploying…**|A run is already going|Watch the **Deploy log** tab|
|The primary button reads **Rebuild image**|The lab is in `Error`|An admin rebuilds the image. See [Create a lab](/docs/user/create-a-lab)|
|**Rebuild image** is grayed out|Rebuilding is admin-only|Ask an admin|
|The deploy failed and the steps do not say why|The detail is in the unsummarized output|Expand **Raw log**. See [Read logs and container stats](/docs/user/logs-and-monitoring)|
|The deploy sat on `Creating the site` for minutes|Site creation is the slow step. It is normal|Wait. In a measured run it took 4m 37s of 4m 52s|
|The bench stays `Deploying` long after the log stopped|The background worker stopped|Tell the operator|
|`This instance has no container — deploy it first`|The bench was never deployed, or it was reaped|Press **Deploy**|

## Reaching a bench

|Symptom|Cause|Fix|
|--|--|--|
|**Open site** reads **Open site — VPN off** and will not press|The address is tunnel-only and your tunnel is down|Turn WireGuard on. See [Register a VPN device](/docs/user/vpn-devices)|
|A site row reads `Unreachable`|Nothing serves that site, or the tunnel is down|Read the hint under the button. It names which|
|A site row reads `Not running`|The container is stopped|Start the bench|
|The private URL times out and the public URL works|The private address is tunnel-only by design|Use the public URL, or turn the tunnel on|
|The public URL 404s|The bench is stopped, so nothing answers the hostname|Start the bench|
|SSH times out|The tunnel is down, or this machine has no device|Run the connection test on **Devices**|
|SSH says `Permission denied`|The password was retyped rather than pasted|Use the copy button on the row|
|SSH and the site both worked yesterday|A redeploy regenerated every password|Reopen **Connection details** and copy again|
|The device status stays `Pending`|The config was never imported|Import the `.conf` and turn the tunnel on|
|The device status turned `Stale`|No handshake for over 5 minutes|Turn the tunnel on again|
|Two machines keep disconnecting each other|One config is in use on both|Register each machine separately|
|**Add device** is refused|The account is at the device cap of 5|Remove a machine you no longer use|

## Inside a bench

|Symptom|Cause|Fix|
|--|--|--|
|No **Open VS Code** button|The lab has code-server switched off|Ask an admin to enable it, then redeploy|
|`Bench must be running to access code-server`|The bench is stopped or still deploying|Start the bench|
|The IDE login page rejects the password|The bench was redeployed since the password was copied|Reopen **Open VS Code**. See [Use code-server](/docs/user/code-server)|
|The IDE tab never loads|The IDE process is not answering|Restart it, or redeploy the bench|
|`Administrator` is refused on the bench site|The admin password came from a different bench|Copy it from this bench's card|
|Files written inside the bench are gone|A redeploy replaced the container and its writable layer|Keep work in git. See [Start, stop and redeploy](/docs/user/lifecycle)|

## Logs and numbers

|Symptom|Cause|Fix|
|--|--|--|
|The Deploy log tab is empty|The bench has never been deployed|Deploy the lab|
|The log stopped streaming mid-run|The live connection dropped|Reload the tab. The record is written either way|
|A run is missing from Deploy history|Logs are cleared after 7 days|Read a newer run, or download the ones you need|
|A history row shows an em dash for duration|The run predates the step markers|Read the raw log|
|No **Build log** tab|Build logs are admin-only|Ask an admin|
|CPU and MEMORY read a dash|The container is not running|Start the bench|
|Health reads `Healthy` on a stopped bench|The last probe ran before the stop|Read the `checked … ago` age beside it|
|CPU reads 100%|The bench is using its whole quota, not the server's|Ask for a larger instance size|

## Credits and leases

These lines apply only while credits are on.

|Symptom|Cause|Fix|
|--|--|--|
|`Not enough credits`|The plan costs more than is available|Pick a shorter plan, or buy credits|
|The refusal names less than the balance shows|Credits are reserved against a running deploy|Stop an instance, or buy credits|
|`You have N instances running, the most your plan allows`|The concurrency cap was hit|Stop one, or buy credits to raise the cap|
|`A lease on this lab cannot run longer than … minutes`|The plan would pass the lab's ceiling|Pick a shorter plan|
|`This bench is already stopping`|The expiry sweep claimed the row first|Wait for the stop, start the bench, then renew|
|`This bench has been torn down. Redeploy it`|The stopped container was reaped after 7 days|Redeploy|
|A purchase fails at the gateway|The server has no gateway keys|Ask the operator. Nothing was charged|
|The deadline passed and the bench is still up|The sweep that stops expired leases is not running|Tell the operator|

## How to report a problem well

Give the person helping you the four things they cannot get themselves.

1. The lab name and the bench id, both on the lab page.
2. The exact message, copied rather than described.
3. Which of the three readings above were true at the time.
4. The step the deploy log stopped on, if a deploy was involved.

A live code-server session is worth more than a description. Send the IDE
address and its password instead of retyping the error.

## Related

* [Quick tour](/docs/user/quick-tour) — which screen owns which task.
* [Register a VPN device](/docs/user/vpn-devices) — the connection test, which answers most reachability questions.
* [Read logs and container stats](/docs/user/logs-and-monitoring) — where the detail behind a failure lives.
* [Connect over SSH and the VPN](/docs/user/connect-ssh-vpn) — the card behind most access problems.
