# WireGuard VPN Setup Guide

This guide walks you through configuring WireGuard VPN for BenchPress. WireGuard is the networking layer that lets users SSH into bench containers and access Frappe web servers securely, without exposing Docker ports to the public internet.

> **Important**: This setup requires a **VPS or dedicated server with a public IP address** (e.g., DigitalOcean, Hetzner, AWS EC2, Linode, Vultr, or any cloud provider). WireGuard VPN does not work on a local machine without a public IP — users outside your network won't be able to connect. If you're running BenchPress locally for personal use, see the [Local Development (No VPN)](#local-development-no-vpn) section at the bottom.

---

## Architecture Overview

```
                    Internet
                       |
                  UDP 51820
                       |
+----------------------------------------------+
|  VPS / SERVER (BenchPress + WireGuard)       |
|  Public IP: e.g., 106.51.76.75              |
|                                              |
|  wg0 interface: 10.10.0.1/24                |
|  Listening on UDP 51820                      |
|                                              |
|  iptables DNAT rules:                        |
|  10.10.0.X:22   --> 172.30.0.Y:22   (SSH)   |
|  10.10.0.X:8000 --> 172.30.0.Y:8000 (Web)   |
|  10.10.0.X:9000 --> 172.30.0.Y:9000 (WS)    |
|                                              |
|  +----------------+  +----------------+      |
|  | Container A    |  | Container B    |      |
|  | 172.30.0.2     |  | 172.30.0.3     |      |
|  | MariaDB+Redis  |  | MariaDB+Redis  |      |
|  | SSH + Frappe   |  | SSH + Frappe   |      |
|  +----------------+  +----------------+      |
|      Docker bridge: 172.30.0.0/24            |
+----------------------------------------------+
                       |
              WireGuard Tunnel
                       |
+----------------------------------------------+
|  USER'S MACHINE (WireGuard Client)           |
|  10.10.0.2/24                                |
|                                              |
|  $ ssh frappe@10.10.0.2                      |
|  $ curl http://10.10.0.2:8000               |
+----------------------------------------------+
```

### Roles

| Component | Role | IP Range |
|-----------|------|----------|
| **VPS / Server** | WireGuard **server** (`wg0`) — runs BenchPress, Docker, and the VPN endpoint | `10.10.0.1` |
| **User's laptop/PC** | WireGuard **client** (peer) — connects via VPN to access containers | `10.10.0.2` - `10.10.0.254` |
| **Docker containers** | Not VPN peers. Reached via iptables DNAT on the server | `172.30.0.0/24` (Docker bridge) |

The containers themselves are **not** WireGuard peers. Traffic from the user's VPN IP is routed to container Docker IPs via iptables NAT rules on the server.

---

## Prerequisites

| Requirement | Why |
|-------------|-----|
| VPS or server with a **public IP** (Ubuntu 20.04+, Debian 11+) | WireGuard kernel module support + clients must reach the server over the internet |
| Root/sudo access on the server | WireGuard and iptables require elevated privileges |
| Docker installed and running on the server | BenchPress containers run on Docker |
| BenchPress app installed on the server | The app manages WireGuard peers automatically |

---

## Step 1: Install WireGuard on the Server

SSH into your VPS and run the following:

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install -y wireguard wireguard-tools
```

### Verify installation

```bash
which wg
# Expected: /usr/bin/wg

which wg-quick
# Expected: /usr/bin/wg-quick

sudo modprobe wireguard
# Should return silently (module loaded)
```

---

## Step 2: Configure Passwordless Sudo on the Server

BenchPress runs background jobs (via RQ workers) as your bench user (e.g., `labs` or `frappe`) on the server. These jobs need to execute `sudo wg`, `sudo iptables`, and `sudo wg-quick` **without a password prompt**. Without this, every deploy will fail with a `sudo: a password is required` error.

```bash
sudo visudo -f /etc/sudoers.d/benchpress
```

Add the following line (replace `labs` with your bench user):

```
labs ALL=(ALL) NOPASSWD: /usr/sbin/iptables, /usr/bin/wg, /usr/bin/wg-quick, /sbin/sysctl
```

Save and exit. Verify it works:

```bash
sudo -n wg show
# Should not prompt for a password
```

---

## Step 3: Initialize WireGuard on the Server

You have two options: **automatic** (recommended) or **manual**. All commands below run on your VPS.

### Option A: Automatic Setup (Recommended)

Run from the Frappe console on your server:

```bash
cd /path/to/your/frappe-bench
bench --site your-site.localhost console
```

```python
from benchpress.wg_manager import setup_wg_server
setup_wg_server()
```

This single command does everything on your server:
1. Generates a server keypair (or validates an existing one)
2. Writes `/etc/wireguard/wg0.conf` with:
   - Server address: `10.10.0.1/24`
   - Listen port: `51820`
   - iptables FORWARD and MASQUERADE rules
3. Enables IP forwarding (`net.ipv4.ip_forward=1`)
4. Brings up the `wg0` interface
5. Saves the server public key and private key to **BenchPress Settings**

### Option B: Manual Setup

If you already have a `wg0` interface running (or prefer to manage the config yourself):

**1. Generate a keypair (skip if you already have one):**

```bash
wg genkey | tee /tmp/wg_private.key | wg pubkey > /tmp/wg_public.key
cat /tmp/wg_private.key
cat /tmp/wg_public.key
```

**2. Create `/etc/wireguard/wg0.conf`:**

```ini
[Interface]
Address = 10.10.0.1/24
ListenPort = 51820
PrivateKey = <your_private_key>
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -s 10.10.0.0/24 -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -s 10.10.0.0/24 -j MASQUERADE
```

**3. Enable IP forwarding:**

```bash
sudo sysctl -w net.ipv4.ip_forward=1

# Make persistent across reboots:
echo "net.ipv4.ip_forward = 1" | sudo tee -a /etc/sysctl.d/99-wireguard.conf
```

**4. Start the interface:**

```bash
sudo chmod 600 /etc/wireguard/wg0.conf
sudo wg-quick up wg0
```

**5. Enable on boot (optional):**

```bash
sudo systemctl enable wg-quick@wg0
```

---

## Step 4: Configure BenchPress Settings

This is the step that connects BenchPress to your WireGuard server. Without these values, every deploy will log `"WireGuard not configured, skipping VPN."`

### Via Frappe Console

```bash
bench --site your-site.localhost console
```

```python
s = frappe.get_doc("BenchPress Settings")

# Required fields -- deploy will skip WireGuard if these are empty
s.wg_server_public_key = "<your_wg0_public_key>"
s.wg_server_endpoint   = "<your_server_public_ip>"

# Optional fields (these have sensible defaults)
s.wg_server_ip   = "10.10.0.1"     # default: 10.10.0.1
s.wg_server_port = 51820           # default: 51820
s.wg_subnet      = "10.10.0.0/24"  # default: 10.10.0.0/24
s.next_wg_ip     = 2               # default: 2 (next peer gets 10.10.0.2)

s.save()
frappe.db.commit()
print("WireGuard settings saved!")
```

### Via Desk UI

Navigate to `/app/benchpress-settings` and fill in the **WireGuard Configuration** section:

| Field | Value | Description |
|-------|-------|-------------|
| **WG Server IP** | `10.10.0.1` | The `wg0` interface address on the server |
| **WG Subnet** | `10.10.0.0/24` | VPN subnet range |
| **WG Server Port** | `51820` | UDP listen port |
| **WG Server Public Key** | *(from step 3)* | The server's public key |
| **WG Server Endpoint** | *(your VPS public IP)* | The public IP/domain clients connect to over the internet |
| **Next WG IP** | `2` | Next available peer IP octet (auto-increments) |

### How to find your VPS public IP

Run this on your server:

```bash
curl -s ifconfig.me
```

### How to find your server's WireGuard public key

```bash
sudo wg show wg0 public-key
```

---

## Step 5: Verify the Setup

```bash
# Check wg0 is running
sudo wg show wg0

# Expected output:
# interface: wg0
#   public key: <your_public_key>
#   private key: (hidden)
#   listening port: 51820
```

```bash
# Check IP forwarding is enabled
sysctl net.ipv4.ip_forward
# Expected: net.ipv4.ip_forward = 1
```

```bash
# Check BenchPress Settings via console
bench --site your-site.localhost console
```

```python
s = frappe.get_cached_doc("BenchPress Settings")
print("Public key:", s.wg_server_public_key)
print("Endpoint:", s.wg_server_endpoint)
# Both must be non-empty for WireGuard to activate during deploy
```

---

## Step 6: Open Firewall Port on the Server

WireGuard uses **UDP port 51820**. Make sure it's open on your VPS:

### UFW (Ubuntu)

```bash
sudo ufw allow 51820/udp
sudo ufw reload
```

### iptables

```bash
sudo iptables -A INPUT -p udp --dport 51820 -j ACCEPT
```

### Cloud provider firewall

Most VPS providers have an additional firewall layer in their dashboard (separate from UFW/iptables on the server itself). You must **also** add an inbound rule for **UDP 51820** there:

| Provider | Where to add the rule |
|----------|----------------------|
| **DigitalOcean** | Networking > Firewalls |
| **AWS EC2** | Security Groups > Inbound Rules |
| **GCP** | VPC Network > Firewall Rules |
| **Hetzner** | Firewalls |
| **Linode** | Firewalls |
| **Vultr** | Firewall |

If you skip this step, clients will get a handshake timeout when trying to connect.

---

## How It Works During Deploy

When you click **Deploy** in the BenchPress UI, the background worker runs this sequence (from `deploy_manager.py`):

```
1. Check BenchPress Settings
   └─ Are wg_server_public_key AND wg_server_endpoint set?
      ├─ No  → Log warning, skip VPN setup (container still works, no VPN access)
      └─ Yes → Continue with VPN setup ↓

2. ensure_wg_running()
   └─ Run `sudo wg show wg0` — if down, bring it up with `sudo wg-quick up wg0`

3. generate_keypair()
   └─ Run `wg genkey` + `wg pubkey` to create a NEW keypair for this bench

4. allocate_ip()
   └─ Read `next_wg_ip` from Settings (e.g., 2)
   └─ Assign 10.10.0.2, increment to 3, save

5. generate_peer_config()
   └─ Build the .conf file the user will download:
      [Interface]
      PrivateKey = <generated_peer_private_key>
      Address = 10.10.0.2/24
      DNS = 1.1.1.1
      [Peer]
      PublicKey = <server_public_key>
      Endpoint = <server_endpoint>:51820
      AllowedIPs = 10.10.0.0/24
      PersistentKeepalive = 25

6. add_peer_to_server()
   └─ Run: sudo wg set wg0 peer <peer_public_key> allowed-ips 10.10.0.2/32

7. setup_wg_routing()
   └─ Get container's Docker IP (e.g., 172.30.0.3)
   └─ Create iptables DNAT rules:
      10.10.0.2:22   → 172.30.0.3:22   (SSH)
      10.10.0.2:8000 → 172.30.0.3:8000 (Frappe web)
      10.10.0.2:9000 → 172.30.0.3:9000 (Socket.io)

8. sync_wg_config()
   └─ Run: sudo wg-quick save wg0 (persist running config to disk)

9. Save to Bench Instance document:
   └─ wg_ip, wg_public_key, wg_private_key, wg_config
```

Both keypairs are generated **on the server**. The peer's private key is stored in the database and embedded in the downloadable `.conf` file. The user does not need to generate any keys themselves.

---

## Connecting as a User

### 1. Download the WireGuard config

From the **Lab Detail** page in BenchPress, click the **Download WireGuard Config** button. This downloads a `.conf` file that is ready to use — no modifications needed.

### 2. Import into WireGuard client

Install the WireGuard client on your device:

| Platform | Install |
|----------|---------|
| **macOS** | [App Store](https://apps.apple.com/us/app/wireguard/id1451685025) or `brew install wireguard-tools` |
| **Windows** | [wireguard.com/install](https://www.wireguard.com/install/) |
| **Ubuntu/Debian** | `sudo apt install wireguard` |
| **iOS** | [App Store](https://apps.apple.com/us/app/wireguard/id1451685025) |
| **Android** | [Play Store](https://play.google.com/store/apps/details?id=com.wireguard.android) |

Import the `.conf` file into the WireGuard app.

### 3. Activate the tunnel

Toggle the VPN on in the WireGuard client.

### 4. Connect to your bench

```bash
# SSH into the container
ssh frappe@10.10.0.2
# Password: shown in the Connection Info panel on the Lab Detail page

# Start Frappe development server
cd frappe-bench
bench start

# Access Frappe in your browser
# http://10.10.0.2:8000
```

---

## Troubleshooting

### "WireGuard not configured, skipping VPN."

**Cause**: `wg_server_public_key` or `wg_server_endpoint` is empty in BenchPress Settings.

**Fix**: Follow [Step 4](#step-4-configure-benchpress-settings) to fill in the settings.

---

### Deploy fails with `sudo: a password is required`

**Cause**: The bench user doesn't have passwordless sudo for `wg`, `iptables`, etc.

**Fix**: Follow [Step 2](#step-2-configure-passwordless-sudo) to configure sudoers.

---

### Deploy fails with `iptables ... returned non-zero exit status 1`

**Cause**: Usually a missing sudoers entry or an iptables backend issue.

**Fix**:
1. Verify sudoers is configured (Step 2)
2. Test the command manually:
   ```bash
   sudo iptables -t nat -L PREROUTING -n
   ```
3. If on Ubuntu 22+, check if `iptables` uses the nftables backend:
   ```bash
   sudo iptables -V
   # If it says "nf_tables", switch to legacy:
   sudo update-alternatives --set iptables /usr/sbin/iptables-legacy
   ```

---

### `wg-quick up wg0` fails with "already exists"

**Cause**: The interface is already running.

**Fix**:
```bash
sudo wg show wg0        # Check if it's up
sudo wg-quick down wg0  # Bring it down
sudo wg-quick up wg0    # Bring it back up
```

---

### Client can't connect (handshake timeout)

**Cause**: UDP 51820 is not reachable from the client's network.

**Fix**:
1. Check firewall: `sudo ufw status` or cloud security group
2. Check port forwarding if behind NAT
3. Verify endpoint IP: run `curl -s ifconfig.me` on your VPS
4. Test UDP reachability from client:
   ```bash
   nc -uzv <server_ip> 51820
   ```

---

### Peer shows `latest handshake: (none)`

**Cause**: The client tunnel is active but no traffic has been exchanged.

**Fix**:
1. Try pinging the server from the client: `ping 10.10.0.1`
2. Check if `AllowedIPs` in the client config includes `10.10.0.0/24`
3. Verify the peer was added on the server: `sudo wg show wg0`

---

### SSH connection refused after connecting VPN

**Cause**: iptables DNAT rules may be missing or the container SSH server isn't running.

**Fix** (run these on your server):
1. Check DNAT rules exist:
   ```bash
   sudo iptables -t nat -L PREROUTING -n | grep <wg_ip>
   ```
2. Check container is running:
   ```bash
   docker ps | grep <bench_name>
   ```
3. Check SSH is running inside the container:
   ```bash
   docker exec <container_id> service ssh status
   ```

---

### IP pool exhausted (max 254 peers)

**Cause**: All IPs from `10.10.0.2` to `10.10.0.254` have been allocated.

**Fix**: Reset the counter after deleting old benches:
```python
# From bench console
s = frappe.get_doc("BenchPress Settings")
s.next_wg_ip = 2  # or whatever the next free IP should be
s.save()
frappe.db.commit()
```

---

## Local Development (No VPN)

If you're running BenchPress on your **local machine** for personal development (not on a VPS), you don't need WireGuard. You can access containers directly via their Docker bridge IPs since you're already on the same machine.

### How it works without WireGuard

1. Leave `wg_server_public_key` and `wg_server_endpoint` empty in BenchPress Settings
2. Deploy a bench normally — WireGuard setup is skipped with a warning
3. The container still runs with SSH, MariaDB, Redis, and Frappe
4. Find the container's Docker IP:
   ```bash
   docker inspect <container_id> --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'
   ```
5. Connect directly:
   ```bash
   ssh frappe@172.30.0.2
   curl http://172.30.0.2:8000
   ```

This works because your local machine is already on the Docker bridge network — no VPN tunnel is needed. However, **only you can access the containers**. Other users on different machines cannot connect without WireGuard, which is why a VPS with a public IP is required for multi-user setups.

---

## Advanced: IPv6 Migration

If you want to switch from IPv4 to IPv6 in the future, here's what changes:

| Component | IPv4 (current) | IPv6 equivalent |
|-----------|----------------|-----------------|
| Server address | `10.10.0.1/24` | `fd10:10::1/64` |
| Peer allocation | `10.10.0.{2-254}` | `fd10:10::{2-ffff}` |
| DNAT rules | `iptables -t nat` | `ip6tables -t nat` |
| AllowedIPs | `10.10.0.0/24` | `fd10:10::/64` |
| Endpoint | `1.2.3.4:51820` | `[2001:db8::1]:51820` |
| IP forwarding | `net.ipv4.ip_forward=1` | `net.ipv6.conf.all.forwarding=1` |
| Docker network | Default IPv4 bridge | `docker network create --ipv6 --subnet fd20::/64 benchpress` |

Code changes required in `wg_manager.py`:
- `allocate_ip()` — hex formatting instead of decimal
- `setup_wg_routing()` / `remove_wg_routing()` — `ip6tables` instead of `iptables`
- `setup_wg_server()` — IPv6 PostUp/PostDown rules
- `_get_container_ip()` — fetch IPv6 address from Docker API

WireGuard itself handles IPv6 natively. The `.conf` file format is the same; only the addresses change.

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `sudo wg show` | Show all WireGuard interfaces and peers |
| `sudo wg show wg0` | Show wg0 status, peers, and traffic |
| `sudo wg-quick up wg0` | Start the WireGuard interface |
| `sudo wg-quick down wg0` | Stop the WireGuard interface |
| `sudo wg set wg0 peer <key> allowed-ips <ip>/32` | Add a peer manually |
| `sudo wg set wg0 peer <key> remove` | Remove a peer |
| `sudo wg-quick save wg0` | Save running config to `/etc/wireguard/wg0.conf` |
| `sudo iptables -t nat -L PREROUTING -n` | List all DNAT rules |
| `curl -s ifconfig.me` | Find your VPS public IP |
| `wg genkey \| tee private.key \| wg pubkey > public.key` | Generate a keypair |
