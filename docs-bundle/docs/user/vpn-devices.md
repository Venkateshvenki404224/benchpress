---
title: Register a VPN device
description: Put a laptop or a phone on the WireGuard network, import the
  config, read the device status, and run the connection test when a site will
  not open.
lastModified: "2026-08-28T11:17:35Z"
lastAuthor: Venkatesh
---
# Register a VPN device

No bench is published to the internet on a tunnel-only address. Register the
machine you work from once, and every bench you own becomes reachable from it.

**Who this is for.** Anybody who cannot reach a bench site, an SSH port or an
IDE on a private address.

**Before you start.** Install the WireGuard client for your platform. You need
nothing else. BenchPress generates the keys.

## Steps

1. Open **Devices** in the sidebar. With no device registered, the page says
   so twice — once in the banner and once in the list.

   ![The BenchPress Devices page at 1280 by 800 pixels with nothing registered. A yellow banner reads, This device is not on the VPN, Register the machine, import the config, then everything below becomes reachable, with an Add this device button. The Registered devices card reports 0 machines and an empty state reading, No machine can reach your benches yet. Register the one you work from and its config arrives immediately. The right column stacks a How this works card listing three numbered steps and a card headed A site will not open with three checks and a Run connection test button.](../images/user/vpn-devices/01-no-devices.png)

   The **How this works** card states the whole model in three lines.

   |#|Step|
   |--|--|
   |1|Register the machine here — it gets a fixed IP on the lab network|
   |2|Import the config into the WireGuard app, or scan the QR on a phone|
   |3|Turn the tunnel on. Sites, SSH and VS Code resolve immediately|

2. Press **Add this device**. Name the machine and pick its type.

   ![The Add this device dialog over the Devices page at 1280 by 800 pixels. The dialog is headed Add this device with the line Two minutes, once per machine. A Device name field holds the typed text Sam — MacBook Pro and a Type dropdown reads Laptop. A dashed placeholder to the left reads, QR appears once the device is registered, and the Download .conf button beside it is grayed out. The paragraph explains that this device gets a fixed IP on the lab network and that nothing else routes through the tunnel. Cancel and Register and connect buttons sit at the foot.](../images/user/vpn-devices/02-add-device.png)

   The name is yours to choose. It is the name every later message uses, so
   name the machine, not the person.

   **Type** accepts one of seven values: `Mobile`, `Laptop`, `Desktop`,
   `Tablet`, `Server`, `IoT` and `Embedded`.

   The QR panel is empty and **Download .conf** is disabled at this point. A
   peer's config does not exist until the peer does.

3. Press **Register and connect**. The config and its QR code appear in the
   same dialog.

   ![The same dialog after registration, at 1280 by 800 pixels. A black and white QR code now fills the left panel, captioned Scan with the WireGuard app, and the Download .conf button beside it is enabled. A green line reads, Registered as 172.27.0.20. Import the config and turn the tunnel on. The Device name and Type fields are grayed out, and the foot of the dialog now offers a single Close button. Behind the dialog the banner has changed to report one machine registered, with a Check again button.](../images/user/vpn-devices/03-registered.png)

   The message names the address the device was given. In the frame it is
   `172.27.0.20`.

   **The QR code encodes the private key.** Treat that image the way you treat
   a password. Do not paste it into a chat channel and do not put it in a
   ticket.

4. Import the config on the machine.

   |Platform|How to import|
   |--|--|
   |macOS|WireGuard app, **Import tunnel(s) from file**, pick the `.conf`|
   |Windows|WireGuard app, **Import tunnel(s) from file**, pick the `.conf`|
   |Linux|Save to `/etc/wireguard/benchpress.conf`, then `sudo wg-quick up benchpress`|
   |iOS|WireGuard app, scan the QR code|
   |Android|WireGuard app, scan the QR code|

5. Turn the tunnel on, then press **Check again** in the banner.

   The chip in the page header turns green and reads `VPN connected` once the
   server has heard from the device.

## Read the device list

Each registered machine is one row.

![The Devices page with one machine registered, at 1280 by 800 pixels. The row reads Sam — MacBook Pro, Laptop, registered 28 Aug, IP 172.27.0.20, Transfer 0 B down and 0 B up, and a gray Pending badge. Config, QR and an overflow button sit under the badge. The banner above still reads, This device is not on the VPN, with the line, 1 machine registered, none with a recent handshake. Turn the tunnel on in your WireGuard client, then check again.](../images/user/vpn-devices/04-device-list.png)

|Column|Value in the frame|Meaning|
|--|--|--|
|Name and type|`Sam — MacBook Pro`, `Laptop`|what you typed when you registered|
|Registered|`28 Aug`|when the peer was created|
|IP|`172.27.0.20`|the fixed tunnel address for this machine|
|Transfer|`0 B ↓ / 0 B ↑`|bytes the server has counted for this peer|
|Status|`Pending`|see the status table below|

**Config** reopens the config text with a download button. **QR** reopens the
scannable code. The overflow button holds **Remove**.

## Run the connection test

Press **Run connection test** when a site will not open. The test checks only
what is yours, so a non-admin gets a real answer.

![The Devices page after running the connection test, at 1280 by 800 pixels. The device row now carries a yellow Stale badge. Under the Run connection test button a bold line reads, First failing check: Peer enabled on the server. Four rows follow: WireGuard server Active, Device registered Active, Peer enabled on the server Error with the hint that Sam — MacBook Pro has stopped talking to the server and to turn its tunnel on again, and Recent handshake Error with the hint that the server has never heard from Sam — MacBook Pro.](../images/user/vpn-devices/05-connection-test.png)

The four checks run in order, and the card names the first one that failed.

|Check|Passes when|
|--|--|
|WireGuard server|the server this tunnel terminates on is up|
|Device registered|this account has at least one device|
|Peer enabled on the server|the device's peer status is `Active`|
|Recent handshake|the last handshake is inside the 5-minute window|

The test never raises an error. A failure is a row with a hint.

## Remove a device

Open the overflow button on the row and choose **Remove**.

![A confirmation dialog over the Devices page at 1280 by 800 pixels, headed Remove this device? The body reads, Sam — MacBook Pro loses VPN access immediately and its tunnel IP goes back to the pool. Registering it again issues a new config. A single black Confirm button spans the foot of the dialog.](../images/user/vpn-devices/06-remove-confirm.png)

Removing is immediate and the address returns to the pool. Registering the
same machine again issues a new key and, usually, a different IP.

## Verify

* The header chip reads `VPN connected`.
* The device row reads `Active` and the transfer counters climb.
* A bench's private URL opens in a browser.
* `ping <the bench WireGuard IP>` answers.

## Troubleshooting

|Symptom|Cause|Fix|
|--|--|--|
|Status stays `Pending`|The config was never imported, or the tunnel is off|Import the `.conf` and turn the tunnel on|
|Status turned `Stale`|No handshake for over 5 minutes|Turn the tunnel on again. WireGuard rekeys about every two minutes|
|Status reads `Disabled`|An administrator disabled the peer|Ask an admin to re-enable it|
|Status reads `Revoked`|The peer was revoked|Register the machine again for a fresh config|
|Two machines drop each other|One config is being used on both|Register each machine separately|
|**Add device** is refused|The account is at the device cap of 5|Remove a machine you no longer use|
|The connection test says `No device to test`|Nothing is registered on this account|Register this machine|
|The tunnel is up and a site still 404s|The bench is stopped, not unreachable|Start the bench|

## Reference

### Device status

|Status|Meaning|
|--|--|
|`Pending`|Registered, never connected|
|`Active`|Handshake inside the last 5 minutes|
|`Stale`|Registered and connected once, silent since|
|`Disabled`|Switched off on the server by an administrator|
|`Revoked`|Withdrawn. The config no longer works|

`Active` is decided by one rule, used by the header chip, the row badge and
the connection test alike: the last handshake is no older than
`VPN Settings.status_poll_interval_min`, which is 5 minutes on this server.

### Limits and defaults

|Setting|Where|Value here|
|--|--|--|
|Devices per account|`Credit Settings.max_devices`|5|
|Handshake window|`VPN Settings.status_poll_interval_min`|5 minutes|
|Device types|fixed in the app|Mobile, Laptop, Desktop, Tablet, Server, IoT, Embedded|

### One device per machine

A WireGuard peer is a single identity. Two machines running the same config
disconnect each other, because the server routes the address to whichever
handshook last. Register every machine separately.

### What a device is underneath

Each device is a **VPN Peer** record owned by your user. The `vpn_management`
app owns the WireGuard server, the address pool and the keys. The Devices page
is a view over the peers you own, and it authorizes by owner rather than by
VPN role, so a BenchPress User can manage their own machines.

### Only the lab network routes through the tunnel

The config routes the lab network and nothing else. Your normal traffic does
not go through BenchPress while the tunnel is on.

## Related

* [Connect over SSH and the VPN](/docs/user/connect-ssh-vpn) — the addresses this tunnel makes reachable.
* [Use code-server](/docs/user/code-server) — the browser IDE, which needs no tunnel.
* [Troubleshooting](/docs/user/troubleshooting) — symptoms across the whole app.
