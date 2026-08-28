---
title: Open the bench site
description: The Sites card, the three states of its Open button, and logging in
  to the Frappe site a deploy created.
lastModified: "2026-08-28T11:17:35Z"
lastAuthor: Venkatesh
---
# Open the bench site

A deploy ends with a working Frappe site. This page opens it and logs in, and
explains the two words the **Open** button uses when it cannot.

**Who this is for.** Anybody whose deploy finished.

**Before you start.** The bench must read `Running`. You need the **Admin
password** from **Connection details** to sign in as `Administrator`.

## Steps

1. Press **Open site** in the lab header. That is the whole task when the
   bench is running and reachable.

   The header button is the fastest route. The rest of this page is for
   reading the site's own state, and for when the button will not press.

2. Open the **Sites** tab for the state behind that button.

   ![The Sites tab of the Frappe CRM demo lab at 1280 by 800 pixels. A single card headed Sites holds one row. The row names the site 89c00d317f31f5e2887d1d9bc80a4ef2.benchpress.cloud, carries two app chips reading Frappe and CRM, and ends in a green Active pill and an Open button. The lab header above reads Frappe CRM demo, Ready, with the chips version-15, 1 GB, 1 vCPU, code-server and SSH, and the buttons Open VS Code and Open site.](../images/user/open-your-site/01-sites-tab.png)

   The row carries four things.

   |Part|Value in the frame|Meaning|
   |--|--|--|
   |Site name|`89c00d31…f2.benchpress.cloud`|the site's own hostname|
   |App chips|`Frappe`, `CRM`|the apps installed on this site|
   |State pill|`Active`|whether the site is serving|
   |Button|**Open**|see the table below|

   The app chips are the lab's app list as it was actually installed. A bench
   built from a larger lab shows more chips.

3. Read the button before pressing it. It never disappears, and it says why
   when it cannot be pressed.

   |Button|Cause|Fix|
   |--|--|--|
   |**Open**|The site is serving and reachable|Press it|
   |**Not running**|The container is stopped|Start the bench|
   |**Unreachable**|The address is tunnel-only and your tunnel is down|Turn WireGuard on|
   |**Unreachable**|Nothing serves this site|Read the hint. The container answers only on its own site|

   A stopped container and a down tunnel are different problems. The button
   never collapses them into one word, because the remedies are different.

4. Sign in on the site. The site is a normal Frappe site with its own login.

   ![The login page of a deployed bench site at 1280 by 800 pixels. A white card on a pale gray background carries the Frappe mark and the heading Login to Frappe. The email field holds Administrator and the password field below it holds a masked value with a Show link at its right. A black Login button spans the card, with a Forgot Password link above it and a Login with Email Link button below.](../images/user/open-your-site/02-site-login.png)

   Use `Administrator` and the **Admin password** from the lab's
   **Connection details** card. That password belongs to this bench alone.

   This login is the site's, not BenchPress's. Your BenchPress account has no
   session here.

5. Work in the site. It opens on whichever app the lab installed.

   ![The deployed bench site after signing in, at 1280 by 800 pixels. Frappe CRM has loaded with Administrator in the account button at the top left and a sidebar listing Dashboard, Leads, Deals, Contacts, Organizations, Notes, Tasks and Call Logs. The Leads list is open and empty, reading No Leads Found with the note that leads can be created with the Create button. A Getting started panel on the right reads Welcome to Frappe CRM, 0 of 9 steps completed, and lists setup tasks beginning with Setup your password.](../images/user/open-your-site/03-site-desk.png)

   In the frame the lab installed Frappe and CRM, so the site opens Frappe CRM
   with an empty Leads list. A site is new, so every list starts empty.

   The Frappe desk is at `/app` on the same hostname.

## Verify

* The Sites row reads `Active` and the button reads **Open**.
* The site opens and shows a login page.
* `Administrator` with the bench's admin password reaches the app.

## Troubleshooting

|Symptom|Cause|Fix|
|--|--|--|
|The Sites card is empty|The deploy has not created the site yet|Watch step 7 on the **Deploy log** tab|
|The row reads `Inactive` and `Not running`|The container is stopped|Start the bench|
|**Open site** in the header reads **Open site — VPN off**|The bench has only a tunnel address|Turn WireGuard on|
|The public URL returns a 404|The bench is stopped, so nothing serves the hostname|Start the bench|
|The private URL times out|It answers only inside the tunnel|Use the public URL, or turn the tunnel on|
|`Administrator` is refused|The password came from another bench|Copy it from this bench's **Connection details**|
|The site loads but every list is empty|The site is new|Nothing is wrong. Create a record|
|The site was fine and now asks for a password that fails|A redeploy replaced the site and its passwords|Copy the new admin password|

## Reference

### The two addresses

|Address|Scheme|Works without the VPN|
|--|--|--|
|Public URL|`https://` hostname|yes|
|Private URL (VPN)|`http://` tunnel address, port 8000|no|

The scheme is the reliable test. Both are built by BenchPress and never typed
by hand, so a plain `http://` address is always the tunnel-only one.

### One site per bench

The container pins its default site and serves only that one. A row naming any
other site has no address, and the button reads `Unreachable` rather than
opening a different site's address from this one's button.

### The site name is a hostname, not a route

The site name is the bench id under the server's domain. It is a label the
site answers to, not something DNS resolves for each bench separately. The
wildcard certificate on the server covers it.

### Which password opens what

|Password|Opens|
|--|--|
|Admin password|`Administrator` on this site|
|SSH password|an SSH session on the container|
|code-server password|the browser IDE|

All three are on **Connection details**, and all three are replaced by a
redeploy.

## Related

* [Connect over SSH and the VPN](/docs/user/connect-ssh-vpn) — where the admin password and both addresses live.
* [Register a VPN device](/docs/user/vpn-devices) — what makes the private address reachable.
* [Start, stop and redeploy](/docs/user/lifecycle) — which action replaces the site.
* [Read a lab page](/docs/user/lab-detail) — the rest of the lab screen.
