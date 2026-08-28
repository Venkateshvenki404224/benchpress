---
title: WireGuard and the VPN plane
description: How the vpn_management app owns the tunnel, what BenchPress
  consumes from it, the measured server and pool values, and why userns-remap
  matters.
lastModified: "2026-08-28T13:08:38Z"
lastAuthor: Venkatesh
---
# WireGuard and the VPN plane

BenchPress does not manage WireGuard. This page says who does, what BenchPress
asks of it, and what an operator has to set.

**Who this is for.** Whoever set the host up and now has to make a laptop
reach a bench.

**Before you start.** `vpn_management` is a required app, declared in
BenchPress's `hooks.py`. It is installed before BenchPress and refuses to
install without `vpn_endpoint_host` in `common_site_config.json` and a
reachable wg-agent socket.

## Who owns what

|Concern|Owned by|Where it lives|
|--|--|--|
|The `wg0` interface|`vpn_management`|the `WireGuard Server` document|
|The IP pool|`vpn_management`|the `Network Pool` document (`pool-wg0`)|
|Peers — bench containers and user devices|`vpn_management`|`VPN Peer` documents|
|IP assignment|`vpn_management`|`IP Allocation`, an atomic row-locked claim|
|Privileged `wg` calls|`vpn_management`|the wg-agent sidecar container|
|Bench and device integration|BenchPress|`benchpress/vpn_adapter.py`|

Three consequences follow, and they are the reason the split exists.

* **No sudo and no host `wg` calls.** The only component that touches
  WireGuard is the wg-agent sidecar. Frappe workers talk to it over a Unix
  socket.
* **A bench container's private key is generated at deploy time** and written
  straight into the container. It is never stored in the database.
* **A device config routes only the pool subnet through the tunnel**, not all
  traffic. A teammate on the VPN keeps their own internet.

## Steps

1. **Confirm the server document.** Open `/app/wireguard-server` in Desk.

   ![The WireGuard Server document wg0 in Frappe Desk. The breadcrumb reads WireGuard Server, wg0, with a green Up badge. Listen Port is 44556, Environment is dev, Address CIDR is 172.27.0.1/16 and Egress Interface is eth0. Below them a Firewall Rules table holds four iptables rules: FORWARD_IN and FORWARD_OUT on the filter table, MASQUERADE on nat POSTROUTING, and REDIRECT on nat PREROUTING.](../images/operator/wireguard-setup/01-wireguard-server.png)

   On this host it reads interface `wg0`, listen port **44556**, address CIDR
   **172.27.0.1/16**, egress interface `eth0`, environment `dev`, and status
   **Up**. Both `provisioned` and `enabled` are set, and `last_reconcile`
   carries the time of the last successful pass.

   The **Firewall Rules** table below them is rendered into the interface's
   `PostUp` and `PostDown`, and seeded from `VPN Settings` when the document
   is created. Four rules ship:

   |#|Rule type|Table|Chain|Spec|
   |--|--|--|--|--|
   |1|`FORWARD_IN`|`filter`|`FORWARD`|`-i {iface} -j ACCEPT`|
   |2|`FORWARD_OUT`|`filter`|`FORWARD`|`-o {iface} -j ACCEPT`|
   |3|`MASQUERADE`|`nat`|`POSTROUTING`|`-o {egress} -j MASQUERADE`|
   |4|`REDIRECT`|`nat`|`PREROUTING`|`-p udp -m multiport …`|

   Rules 1 and 2 are what step 4 of
   [Prerequisites](/docs/operator/prerequisites) turns IP forwarding on for. A
   laptop reaches a bench through the host, and without both the forward rule
   and the kernel switch the packet is dropped.

2. **Confirm the pool.** Open `/app/network-pool`. The pool `pool-wg0` covers
   `172.27.0.0/16` with gateway `172.27.0.1`, allocates sequentially, and
   holds **65,534** addresses.

3. **Set the endpoint host.** `vpn_endpoint_host` in
   `common_site_config.json` is the address a client dials. It must be
   reachable from wherever your teammates are, so it is a public address or
   name, not `127.0.0.1`.

4. **Open the port.**

   ```bash
   sudo ufw allow 44556/udp
   ```

   Open it on the cloud firewall too. `ufw` cannot see that layer, and a
   closed security group produces exactly the same symptom as a closed `ufw`
   rule: a peer that exists and never handshakes.

5. **Enable Docker userns-remap.** See
   [Container root is not host root](#container-root-is-not-host-root). Do this
   before the first deploy, not after.

## Verify

```bash
bench --site <site> execute benchpress.diagnostics.check_vpn_server
```

A pass reads `WireGuard server 'wg0' configured`. Then have somebody register
a device and run the connection test on the **Devices** page — that check
exercises the whole path, which no server-side reading does. See
[Register a VPN device](/docs/user/vpn-devices).

## What BenchPress asks of the VPN plane

BenchPress only consumes the plane, through `benchpress/vpn_adapter.py`.

|BenchPress action|What it asks for|
|--|--|
|Deploy|Generate a keypair, register a `VPN Peer` for the container — the insert claims the IP — write the client config into the container, and bring `wg0` up inside it|
|Delete or redeploy|Remove the bench's peer, which frees the allocation|
|Devices page|Add, remove, list and fetch a config. These are thin wrappers over `VPN Peer` documents|

Eighteen peers exist on this host. A bench and a laptop are both peers — the
pool does not distinguish them, which is why a bench and a device compete for
the same 65,534 addresses.

## Container root is not host root

A lab user gets **root inside their bench container**. That is deliberate: a
bench is useless without it. `create_bench_container` avoids `privileged`, but
without user-namespace remapping, in-container UID 0 is host UID 0, and a
container escape becomes a host-root escape.

Two ways to close it. Either is enough.

**Sysbox.** `default_bench_runtime` ships as `sysbox`, and `sysbox-runc` gives
each container its own user namespace without changing the daemon. This is the
default path, and the one this host uses.

**Docker userns-remap.** Maps container root to an unprivileged host UID range
for every container on the daemon.

1. Add to `/etc/docker/daemon.json`, creating the file if it does not exist:

   ```json
   { "userns-remap": "default" }
   ```

2. Restart Docker: `sudo systemctl restart docker`

3. Confirm the pass line:

   ```bash
   bash apps/benchpress/setup.sh <site> --strict
   ```

**Turn userns-remap on before your first deploy.** It re-roots Docker's
storage under a remapped subdirectory of `/var/lib/docker`. The remapped
daemon no longer sees existing containers, images or volumes — deployed labs
and `benchpress-mariadb-data` included. Nothing is deleted, but everything has
to be redeployed. If benches already exist, back their data up and plan a
redeploy of every one of them before you flip the switch.

Running the Docker daemon rootless is an accepted alternative. The whole
daemon runs as an unprivileged user, so container root is not host root even
more plainly. `setup.sh` reports a pass on a rootless host.

## Troubleshooting

|Symptom|Cause|Fix|
|--|--|--|
|A deploy fails at `Configuring WireGuard VPN`|The wg-agent container is down, or the server document is not `Up`|Start wg-agent, then check `WireGuard Server` status in Desk|
|A peer exists but never handshakes|UDP 44556 is closed, or `vpn_endpoint_host` is wrong|Open the port on both firewalls, and set an address a client can actually dial|
|`IP pool exhausted`|65,534 allocations are claimed, or stale peers hold them|Review `IP Allocation` and delete peers for benches that no longer exist|
|The interface is out of sync with the peers|A reconcile failed|`vpn_management` reconciles on peer change. Read its error log in Desk|
|`wg-quick up wg0` reports `wg0 already exists` during a deploy|The container entrypoint won the race|Retry the deploy. It is intermittent, not a defect of the step|
|`setup.sh --strict` refuses to continue|Neither userns-remap nor rootless is on|Enable one, or accept the risk knowingly on a throwaway box|

## Reference

Measured on this host.

|Item|Value|
|--|--|
|Interface|`wg0`|
|Listen port|44556/UDP|
|Server address|`172.27.0.1/16`|
|Pool|`172.27.0.0/16` (`pool-wg0`)|
|Gateway|`172.27.0.1`|
|Addresses in the pool|65,534|
|Allocation strategy|sequential|
|Egress interface|`eth0`|
|Endpoint host|`vpn_endpoint_host` in `common_site_config.json`|
|Adapter|`benchpress/vpn_adapter.py`|

For anything deeper than the table above, read the `vpn_management` app's own
documentation. It owns every one of these values.

## Related

* [Register a VPN device](/docs/user/vpn-devices) — the same tunnel, from a user's laptop.
* [Production safety](/docs/operator/production-safety) — the container privilege boundary in full.
* [Diagnostics](/docs/operator/diagnostics) — the `vpn_server` check and what it does not cover.
