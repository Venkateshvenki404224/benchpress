# VPN Device Management

BenchPress supports persistent VPN device registration. Each device (laptop, phone, tablet) gets its own WireGuard identity that works across all your lab containers.

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

From the sidebar, click **Devices**.

![Devices page](images/devices.png)

### Click "Add Device"

A dialog appears with the following fields:

| Field | Required | Description |
|-------|----------|-------------|
| **Device Name** | Yes | A friendly name for your device (e.g., "My MacBook") |
| **Device Type** | Yes | The type of device: Mobile, Laptop, Desktop, Tablet, Server, IoT, Embedded |
| **Auto Generate Keypair** | Default: checked | Let BenchPress generate the WireGuard keys |
| **WireGuard Public Key** | Only if auto-generate is unchecked | Provide your own public key |

Click **Add Device** to register.

---

## Device Card

After registering, each device appears as a card showing:


| Element | Description |
|---------|-------------|
| **Device name** | The friendly name you chose |
| **Type badge** | Device type (Laptop, Mobile, etc.) |
| **Status** | Active (green) or inactive (gray) |
| **WireGuard IP** | Allocated VPN IP (e.g., `10.10.0.3`) |
| **Received / Sent** | Data transfer stats from WireGuard |

---

## Getting Your WireGuard Config

### Option 1: Show Configuration

Click the menu icon (three dots) on a device card and select **Show Configuration**.

A dialog opens with:
- The full WireGuard config text (left side)
- A QR code for mobile import (right side)


### Option 2: Download Tunnel File

Click the menu icon and select **Download Tunnel File**. This downloads a `.conf` file that you can import directly into the WireGuard app on any platform.

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

Click the menu icon on a device card and select **Delete**.

A confirmation dialog appears:

> "Are you sure you want to remove [device_name]? This will revoke its VPN access immediately."

Click **Remove Device** to confirm. This will:
1. Remove the WireGuard peer from the server
2. Deallocate the VPN IP
3. Delete the Bench Device doc

> After removal, the device can no longer connect to any bench containers via VPN.

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

1. Download a fresh config file (the config may have been generated before WireGuard server was fully set up)
2. Verify the server's UDP port 51820 is open: `sudo ufw status`
3. Check the WireGuard server is running: `sudo wg show wg0`

### QR code not scanning

- Ensure your phone camera can see the entire QR code
- Try increasing screen brightness
- Use the "Download Tunnel File" option instead and transfer via AirDrop/email

---

## Next Steps

- [Connecting to Benches](connecting-to-benches.md) — Use your device to SSH into benches
- [Getting Started](getting-started.md) — Initial setup guide
