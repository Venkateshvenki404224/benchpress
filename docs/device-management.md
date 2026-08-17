# VPN Device Management

BenchPress supports persistent VPN device registration. Each device (laptop, phone, tablet) gets its own WireGuard identity that works across all your lab containers.

Under the hood every device is a **VPN Peer** document in the
**vpn_management** app, which owns the WireGuard server, the IP pool, and
key management — see [WireGuard Setup](wireguard-setup.md). The Devices page
below is unchanged; it is a thin view over those peers.

---

## Why Register Devices?

Instead of getting a new WireGuard config every time you deploy a bench, you register your devices once and they can access all your containers automatically. Each device gets:

- A persistent WireGuard keypair
- A dedicated VPN IP address
- A downloadable `.conf` file for the WireGuard app
- A QR code for mobile import

---

## Registering a New Device

### Navigate to the Devices page

From the sidebar, click **Devices**. The top of the screen states whether your tunnel is up,
and what to do when it is not.

![Devices page](images/devices.png)

### Click "Add this device"

A dialog appears with two fields:

| Field | Required | Description |
|-------|----------|-------------|
| **Device name** | Yes | A friendly name for your device (e.g., "My MacBook") |
| **Type** | Yes | Mobile, Laptop, Desktop, Tablet, Server, IoT or Embedded |

Keys are generated for you — the private key never leaves the config you download. Click
**Register and connect**; the configuration and its QR code appear in the same dialog, because
a peer's config does not exist until the peer does.

---

## The device list

After registering, each device is a row in **Registered devices**:

| Element | Description |
|---------|-------------|
| **Device name** | The friendly name you chose |
| **Type** | Device type (Laptop, Mobile, etc.) |
| **Status** | A themed badge — Active while the handshake is fresh, Stale once it is not |
| **WireGuard IP** | Allocated VPN IP (e.g., `172.27.0.3`) |
| **Transfer** | Received / sent counters from WireGuard |
| **Registered** | When the device was added |

---

## Getting Your WireGuard Config

### Option 1: Config

Click **Config** on the device's row. A dialog opens with the full WireGuard config text and a
**Download .conf** button.

### Option 2: QR

Click **QR** on the device's row for a scannable code — the panel forces a white background so
a phone camera can read it in dark mode too.

### Importing the config

| Platform | How to import |
|----------|--------------|
| **macOS** | WireGuard app → Import tunnel(s) from file → select `.conf` |
| **Windows** | WireGuard app → Import tunnel(s) from file → select `.conf` |
| **Linux** | Copy to `/etc/wireguard/benchpress.conf` → `sudo wg-quick up benchpress` |
| **iOS** | WireGuard app → scan QR code from the config dialog |
| **Android** | WireGuard app → scan QR code from the config dialog |

---

## Removing a Device

Open the `⋯` menu on the device's row and select **Remove**.

A confirmation dialog appears:

> "Are you sure you want to remove [device_name]? This will revoke its VPN access immediately."

Click **Remove Device** to confirm. This will:
1. Delete the device's VPN Peer
2. Free its IP allocation
3. Sync the change to the WireGuard interface

> After removal, the device can no longer connect to any bench containers via VPN.

---

## When a site will not open

The **A site will not open?** card runs a connection test against your own tunnel: the VPN
server, whether this account has a device registered, whether its peer is active, and whether
there has been a recent handshake. It names the first failing check and what to do about it,
rather than leaving you to guess which half of the path is down.

---

## Multiple Devices

You can register as many devices as you need. Common setups:

| Device | Use Case |
|--------|----------|
| **Work Laptop** | Primary development via SSH + VS Code |
| **Personal Laptop** | Backup access |
| **Mobile Phone** | Quick checks via WireGuard app + browser |
| **Tablet** | Testing responsive layouts |

Each device gets its own IP and can access all your running bench containers simultaneously.

---

## Troubleshooting

### Device shows as inactive

- Check that the WireGuard tunnel is active on the device
- Verify the server endpoint IP is correct in the config

### Cannot connect after registering

1. Download a fresh config file (the config may have been generated before the WireGuard server was fully set up)
2. Verify the server's UDP port 44556 is open: `sudo ufw status`
3. Check the **WireGuard Server** DocType (vpn_management) shows the interface as active

### QR code not scanning

- Ensure your phone camera can see the entire QR code
- Try increasing screen brightness
- Use the "Download Tunnel File" option instead and transfer via AirDrop/email

---

## Next Steps

- [Connecting to Benches](connecting-to-benches.md) — Use your device to SSH into benches
- [Getting Started](getting-started.md) — Initial setup guide
