# WireGuard / VPN Setup

BenchPress no longer manages WireGuard itself. All VPN mechanics — the
`wg0` interface, peers, IP allocation, and key management — are owned by the
**vpn_management** app, which BenchPress declares as a required app.

---

## How it works now

| Concern | Owned by | Where |
|---------|----------|-------|
| WireGuard interface (`wg0`) | vpn_management | **WireGuard Server** DocType |
| IP pool (`172.27.0.0/16` in dev) | vpn_management | **Network Pool** DocType (`pool-wg0`) |
| Peers (bench containers and user devices) | vpn_management | **VPN Peer** DocType |
| IP assignment | vpn_management | **IP Allocation** (atomic, row-locked claim) |
| Privileged `wg` calls | vpn_management | **wg-agent** sidecar container |
| Bench/device integration | BenchPress | [`benchpress/vpn_adapter.py`](../benchpress/vpn_adapter.py) |

Key differences from the legacy embedded stack:

- **No sudo, no host `wg` calls.** The only component that touches WireGuard
  is the wg-agent sidecar; the Frappe workers talk to it over a Unix socket.
- **Port `44556`** (UDP) instead of `51820`. Open it in your firewall:
  `sudo ufw allow 44556/udp`.
- **Pool `172.27.0.0/16`** instead of `10.10.0.0/24`.
- Container private keys are generated at deploy time and written straight
  into the container — they are never persisted in the database.
- Device configs route **only the VPN pool subnet** through the tunnel, not
  all traffic.

---

## Configuring the VPN

Open the vpn_management DocTypes in Frappe Desk:

1. **WireGuard Server** — the `wg0` interface: address CIDR, listen port,
   server public key, reconcile status.
2. **Network Pool** — the IP range peers are allocated from.
3. **VPN Peer** — one row per bench container or registered device.
4. **IP Allocation** — the claim ledger; an allocation is freed when its
   peer is deleted.

The server's public endpoint host comes from `vpn_endpoint_host` in site
config (`common_site_config.json`); vpn_management refuses to install
without it and without a reachable wg-agent socket.

---

## What BenchPress does

BenchPress only *consumes* the VPN plane through `benchpress/vpn_adapter.py`:

- **Deploy**: generates a keypair, registers a VPN Peer for the container
  (the insert claims the IP), writes the client conf into the container, and
  brings up `wg0` inside it.
- **Delete/redeploy**: removes the bench's peer so the allocation is freed.
- **Devices page**: the add/remove/list/config APIs are thin wrappers over
  VPN Peer documents — see [Device Management](device-management.md).

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Deploy fails at "Configuring WireGuard VPN" | wg-agent container running? `WireGuard Server` status in Desk? |
| Peer exists but no handshake | Is UDP `44556` open? Correct `vpn_endpoint_host`? |
| IP pool exhausted | Review **IP Allocation** rows; delete stale VPN Peers to free IPs |
| Interface out of sync with peers | vpn_management reconciles on peer changes; check its error logs in Desk |

For anything deeper, consult the vpn_management app's own documentation.
