---
title: Connect over SSH and the VPN
description: The connection card on a lab page — two addresses, the SSH command,
  the three passwords, and which of them work without the tunnel.
lastModified: "2026-08-28T22:10:21+05:30"
lastAuthor: Venkatesh
---
# Connect over SSH and the VPN

A running bench publishes one card with everything needed to reach it. This
page reads that card field by field and gets you a shell inside the container.

**Who this is for.** Anybody whose bench has finished deploying.

**Before you start.** The bench must read `Running`. Register this machine on
the VPN first — see [Register a VPN device](/docs/user/vpn-devices). Only one
field on the card works without the tunnel.

## Steps

1. Open the lab and stay on the **Dashboard** tab. **Connection details** is
   the second card in the left column. Every secret starts masked.

   ![The Connection details card on a BenchPress lab page at 1280 by 800 pixels, seen as a non-admin user. A note under the card header reads that the public URL works from anywhere, everything else is reachable only over the VPN, and passwords are regenerated on every redeploy. Nine rows are listed: Public URL, Private URL (VPN) as http colon slash slash 172.27.0.19 colon 8000, WireGuard IP 172.27.0.19, Runtime sysbox, a code-server address, SSH as ssh intern at 172.27.0.19, and then SSH password, Admin password and code-server password, all three drawn as rows of dots. A Reveal secrets button sits in the card header and every row ends in a copy button.](../images/user/connect-ssh-vpn/01-connection-details.png)

   The card carries nine rows. Four are addresses, one is the runtime, one is
   a command, and three are passwords.

   |Row|Value in the frame|Needs the VPN|
   |--|--|--|
   |Public URL|`https://05c166d4…f.benchpress.cloud`|no|
   |Private URL (VPN)|`http://172.27.0.19:8000`|yes|
   |WireGuard IP|`172.27.0.19`|yes|
   |Runtime|`sysbox`|—|
   |code-server|`https://ide-05c166d4….benchpress.cloud`|no|
   |SSH|`ssh intern@172.27.0.19`|yes|
   |SSH password|masked|—|
   |Admin password|masked|—|
   |code-server password|masked|—|

   The scheme tells you which kind of address you are holding. A `https://`
   hostname answers from anywhere. A plain `http://` tunnel address answers
   only for a device on the WireGuard network.

2. Press **Reveal secrets** to unmask all three passwords at once.

   ![The same Connection details card after pressing Reveal secrets, at 1280 by 800 pixels. The header button now reads Hide secrets. The three password rows show plain text instead of dots: SSH password, Admin password and code-server password each hold a random mixed-case string of twelve to twenty characters. Every other row is unchanged, and the copy button is still at the end of each row.](../images/user/connect-ssh-vpn/02-revealed.png)

   One toggle drives the whole column. The button becomes **Hide secrets**
   while the passwords are shown.

   The reveal state lives on the screen, not on the account. Navigate away and
   back and the passwords are masked again.

3. Press the copy button at the end of a row instead of selecting the text.
   The icon turns into a check mark for two seconds to confirm the copy.

   Copying works whether or not the row is revealed. You do not have to show a
   password to paste it.

4. Turn the WireGuard tunnel on in your client. Nothing below this step works
   with the tunnel down.

5. Run the SSH command from the card. Paste the SSH password when it asks.

   ```bash
   ssh intern@172.27.0.19
   ```

   The username is your email address with the domain removed, lowercased,
   stripped of anything that is not a valid Linux username character, and cut
   to 32 characters. `John.Doe@example.com` becomes `johndoe`.

6. Work in the bench. The bench is at `/home/frappe/frappe-bench` and its
   services are already running. The deploy started them at step 10.

   ```bash
   cd /home/frappe/frappe-bench
   bench --site <site> list-apps
   ```

7. Open the site in a browser to log in to Frappe. Use the public URL from
   anywhere, or the private URL over the tunnel. Sign in as `Administrator`
   with the **Admin password** from the card.

## Verify

* `ssh <username>@<WireGuard IP>` gives a shell prompt inside the container.
* The site opens at the public URL and accepts `Administrator` with the admin
  password.
* With the tunnel off, the public URL still opens and the private URL times
  out. That difference is the tunnel working as designed.

## Troubleshooting

|Symptom|Cause|Fix|
|--|--|--|
|The card is not on the page|It renders for a deployed bench only|Deploy the lab first|
|Every password reads `—`|The bench has no stored credential yet|Wait for the deploy to reach `Deploy complete`|
|SSH times out|The tunnel is down, or this machine has no device|Turn WireGuard on, then run the connection test on **Devices**|
|SSH says `Permission denied`|The password was retyped, not pasted|Use the row's copy button|
|SSH worked yesterday and fails today|A redeploy regenerated the passwords|Reopen the card and copy them again|
|The private URL never answers|It is tunnel-only by design|Use the public URL, or turn the tunnel on|
|The public URL 404s|The bench is stopped, so nothing serves the hostname|Start the bench|
|`Administrator` is refused on the site|The admin password was taken from another bench|Copy it from this bench's card|

## Reference

### What each field is

|Field|Source|Notes|
|--|--|--|
|Public URL|the bench hostname behind the reverse proxy|HTTPS, works without the VPN|
|Private URL (VPN)|the WireGuard address and port 8000|plain HTTP inside the tunnel|
|WireGuard IP|claimed from the pool at deploy step 5|one address per bench|
|Runtime|the container runtime the bench runs on|`sysbox` on this server|
|code-server|the browser IDE address|see [Use code-server](/docs/user/code-server)|
|SSH|`ssh <username>@<WireGuard IP>`|the username is derived from your email|
|SSH password|generated per deploy|for the SSH login above|
|Admin password|generated per deploy|for `Administrator` on the Frappe site|
|code-server password|generated per deploy|for the IDE login page|

### The passwords are regenerated on every redeploy

A redeploy replaces the container, and the new container gets new credentials.
A **Stop** followed by a **Start** keeps them, because that is the same
container. Never write a bench password into a script.

### VS Code Remote SSH

The card's SSH command is a normal SSH target, so the Remote-SSH extension
takes it as it is.

1. Install the **Remote - SSH** extension.
2. Run **Remote-SSH: Connect to Host**.
3. Enter `<username>@<WireGuard IP>`.
4. Paste the SSH password.
5. Open `/home/frappe/frappe-bench`.

The tunnel has to be up first. For an IDE that needs no local install, use
code-server instead.

### Who can see the card

The endpoint behind it checks bench access on every call. You see your own
benches. An admin sees every bench on the server.

## Related

* [Register a VPN device](/docs/user/vpn-devices) — the tunnel every field here depends on.
* [Use code-server](/docs/user/code-server) — the browser IDE and its own password.
* [Start, stop and redeploy](/docs/user/lifecycle) — which actions regenerate these passwords.
* [Read a lab page](/docs/user/lab-detail) — the rest of the screen this card sits on.
