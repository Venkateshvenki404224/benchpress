# Headscale Installation and BenchPress Integration Guide

This guide documents how to install and validate Headscale for the BenchPress Phase 2 private developer access spike.

BenchPress networking is intentionally split into two layers:

1. **Public browser access**: public HTTPS URLs for Frappe/ERPNext sites, handled by Traefik/Caddy or another reverse proxy.
2. **Private developer access**: SSH, code-server, internal ports, and team/device access through Headscale/Tailscale-compatible networking.

Headscale belongs to layer 2. It is not a replacement for public browser URL routing.

---

## 1. License and product/legal check

### Headscale license

Headscale is licensed under **BSD-3-Clause**.

Verified source:

- Repository: <https://github.com/juanfont/headscale>
- SPDX license: `BSD-3-Clause`
- License file: <https://github.com/juanfont/headscale/blob/main/LICENSE>

The BSD-3-Clause license permits redistribution and use in source and binary forms, with or without modification, as long as the license conditions are followed.

### Compatibility with BenchPress

BenchPress is MIT-licensed. BSD-3-Clause is generally compatible with MIT from a product and distribution perspective.

For BenchPress, this means we can integrate with Headscale, document Headscale setup, and optionally ship scripts/configuration around it, provided we comply with BSD-3-Clause obligations.

### Required obligations

If BenchPress redistributes Headscale source code or binaries, we must:

1. Keep the Headscale copyright notice.
2. Keep the BSD-3-Clause license text.
3. Include the license notice in documentation or other materials when distributing binaries.
4. Do not use the Headscale copyright holder or contributors' names to endorse BenchPress without written permission.

Recommended BenchPress action before bundling binaries:

- Add `THIRD_PARTY_NOTICES.md` or `licenses/headscale-BSD-3-Clause.txt`.
- Mention that Headscale is a third-party project.
- Link to the upstream repository and license.

### Tailscale naming/trademark caution

Headscale's README states that Headscale is **not associated with Tailscale Inc.**

BenchPress should avoid marketing language that implies BenchPress, Headscale, or this integration is officially endorsed by Tailscale.

Safe wording:

- “Tailscale-compatible private networking”
- “Headscale-based private access”
- “Self-hosted WireGuard control plane using Headscale”

Avoid wording like:

- “Official Tailscale integration”
- “Tailscale-powered BenchPress”
- “Tailscale Cloud replacement”

Also note that Headscale is open source, but proprietary Tailscale GUI clients may have their own terms. BenchPress should not bundle proprietary Tailscale clients without a separate legal review.

### PM conclusion

No blocking license issue was found for using Headscale with BenchPress, as long as we:

- Treat Headscale as a third-party dependency.
- Preserve BSD-3-Clause notices if we redistribute it.
- Avoid endorsement/trademark confusion.
- Prefer installing Headscale from upstream releases/packages instead of vendoring the binary into BenchPress initially.

---

## 2. Local smoke test result

A local end-to-end smoke test was run with Headscale `v0.28.0` using a standalone binary and SQLite.

Validated successfully:

- Downloaded Headscale Linux binary from upstream GitHub release.
- Ran `headscale version`.
- Created minimal `config.yaml`.
- Ran `headscale configtest`.
- Started Headscale server on localhost.
- Verified `/version` HTTP endpoint.
- Created a Headscale user.
- Created a pre-auth key.
- Created an API key.
- Queried `/api/v1/user` with Bearer token.

Smoke test result:

```text
HEADSCALE_E2E_OK
```

Issues found during smoke test:

1. `dns.nameservers.global` is required when `dns.override_local_dns` is `true`.
   - Fix: include global DNS nameservers in config.
2. In Headscale `v0.28.0`, `preauthkeys create --user` expects a numeric user ID, not the username.
   - Fix: use the ID from `headscale users list` or the API response.
3. The older `acls` policy syntax worked in the smoke test. `grants` caused a config parsing error in this exact minimal test config/version.
   - Fix: start with `acls` for the first BenchPress spike, then evaluate `grants` separately.

These are not blockers, but they must be documented in BenchPress preflight/doctor checks.

---

## 3. Recommended deployment model for BenchPress

For the first BenchPress Headscale spike, use this architecture:

```text
Developer machine
  |
  | Tailscale client using Headscale login server
  v
Headscale server
  |
  | private tailnet control plane
  v
BenchPress host / subnet router
  |
  v
Bench containers: SSH, code-server, internal services
```

Recommended first spike approach:

- Run Headscale on the BenchPress host or a dedicated private networking host.
- Use Headscale for developer device registration and ACLs.
- Keep public browser access separate through Traefik/Caddy.
- Start with host/subnet-router style access before running `tailscaled` inside every bench container.

Reason:

- Lower container privilege risk.
- Easier cleanup.
- Easier operational model.
- Better fit with existing BenchPress Docker network.

---

## 4. Installation prerequisites

Target OS:

- Ubuntu 22.04+ or Debian 12+ recommended.

Required:

- Root/sudo access.
- Public DNS name for the Headscale server.
- HTTPS/TLS certificate, either directly in Headscale or via a reverse proxy.
- Open TCP port for Headscale HTTPS, usually `443`.
- SQLite for simple installs, PostgreSQL for larger/team installs if needed later.

Recommended DNS names:

```text
headscale.example.com       # Headscale control server
*.bench.example.com         # Public browser access handled separately by Traefik/Caddy
```

Important:

- `dns.base_domain` must be different from `server_url` domain.
- Example:
  - `server_url`: `https://headscale.example.com`
  - `dns.base_domain`: `internal.bench.example.com`

---

## 5. Install Headscale from upstream release binary

Set variables:

```bash
export HEADSCALE_VERSION="0.28.0"
export HEADSCALE_ARCH="amd64" # use arm64 on ARM servers
```

Download and install:

```bash
curl -L \
  "https://github.com/juanfont/headscale/releases/download/v${HEADSCALE_VERSION}/headscale_${HEADSCALE_VERSION}_linux_${HEADSCALE_ARCH}" \
  -o /tmp/headscale

sudo install -m 0755 /tmp/headscale /usr/local/bin/headscale
headscale version
```

Create system user and directories:

```bash
sudo useradd \
  --system \
  --user-group \
  --home-dir /var/lib/headscale \
  --create-home \
  --shell /usr/sbin/nologin \
  headscale || true

sudo mkdir -p /etc/headscale /var/lib/headscale /var/run/headscale
sudo chown -R headscale:headscale /var/lib/headscale /var/run/headscale
sudo chmod 750 /var/lib/headscale
```

---

## 6. Minimal production-style config

Create `/etc/headscale/config.yaml`:

```yaml
server_url: https://headscale.example.com
listen_addr: 127.0.0.1:8080
metrics_listen_addr: 127.0.0.1:9090
grpc_listen_addr: 127.0.0.1:50443
grpc_allow_insecure: false

noise:
  private_key_path: /var/lib/headscale/noise_private.key

prefixes:
  v4: 100.64.0.0/10
  v6: fd7a:115c:a1e0::/48

derp:
  server:
    enabled: false
  urls:
    - https://controlplane.tailscale.com/derpmap/default
  auto_update_enabled: true

database:
  type: sqlite
  sqlite:
    path: /var/lib/headscale/db.sqlite
    write_ahead_log: true

policy:
  mode: file
  path: /etc/headscale/acl.hujson

dns:
  magic_dns: true
  base_domain: internal.bench.example.com
  override_local_dns: true
  nameservers:
    global:
      - 1.1.1.1
      - 1.0.0.1
  search_domains: []
  extra_records: []

unix_socket: /var/run/headscale/headscale.sock
unix_socket_permission: "0770"

disable_check_updates: false

log:
  level: info
  format: text
```

Update these values before production use:

- `server_url`
- `dns.base_domain`
- DNS nameservers if your infrastructure requires custom DNS
- database settings if moving from SQLite to PostgreSQL

---

## 7. Minimal ACL policy for first spike

Create `/etc/headscale/acl.hujson`:

```json
{
  "groups": {
    "group:admins": ["admin@example.com"]
  },
  "tagOwners": {
    "tag:bench": ["group:admins"]
  },
  "acls": [
    {
      "action": "accept",
      "src": ["*"],
      "dst": ["*:*"]
    }
  ]
}
```

This ACL is intentionally permissive for the first technical spike.

Before production/private beta, replace it with a stricter model:

- Admins can access all benches.
- Users can access only their own benches.
- Client/demo users can access only assigned benches.
- Internal service ports are restricted.

---

## 8. Validate configuration

```bash
sudo headscale --config /etc/headscale/config.yaml configtest
```

Expected:

```text
# no fatal error
```

If you see:

```text
dns.nameservers.global must be set when dns.override_local_dns is true
```

Fix by adding:

```yaml
dns:
  override_local_dns: true
  nameservers:
    global:
      - 1.1.1.1
      - 1.0.0.1
```

---

## 9. systemd service

Create `/etc/systemd/system/headscale.service`:

```ini
[Unit]
Description=Headscale coordination server for Tailscale-compatible private networking
Documentation=https://headscale.net/
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=headscale
Group=headscale
ExecStart=/usr/local/bin/headscale --config /etc/headscale/config.yaml serve
Restart=on-failure
RestartSec=5s

# Basic hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=/var/lib/headscale /var/run/headscale
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now headscale
sudo systemctl status headscale --no-pager
```

Check logs:

```bash
journalctl -u headscale -f
```

---

## 10. Reverse proxy example

Headscale can listen on `127.0.0.1:8080`, with Traefik/Caddy/Nginx handling public TLS.

Example Nginx server block:

```nginx
server {
    listen 443 ssl http2;
    server_name headscale.example.com;

    ssl_certificate /etc/letsencrypt/live/headscale.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/headscale.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

BenchPress note:

- Keep this separate from the public Frappe site reverse proxy.
- Public site routing is Phase 1.
- Headscale private networking is Phase 2.

---

## 11. Create Headscale users

Create an admin/user namespace:

```bash
sudo headscale users create benchpress-admin
sudo headscale users list
```

In Headscale `v0.28.0`, many commands use the numeric user ID.

Example output:

```text
ID | Username
1  | benchpress-admin
```

Use `1` in commands that require `--user`.

---

## 12. Create a pre-auth key

```bash
sudo headscale preauthkeys create --user 1 --expiration 1h
```

For reusable developer onboarding during a test:

```bash
sudo headscale preauthkeys create --user 1 --reusable --expiration 24h
```

For ephemeral nodes:

```bash
sudo headscale preauthkeys create --user 1 --ephemeral --expiration 1h
```

For tagged bench/private service nodes:

```bash
sudo headscale preauthkeys create --user 1 --tags tag:bench --expiration 1h
```

Store generated auth keys securely. Do not log them in BenchPress job logs.

---

## 13. Connect a client device

On a developer machine with Tailscale client installed:

```bash
tailscale up \
  --login-server https://headscale.example.com \
  --authkey <PRE_AUTH_KEY>
```

Verify on the Headscale server:

```bash
sudo headscale nodes list
```

---

## 14. API key setup

Create an API key:

```bash
sudo headscale apikeys create --expiration 90d
```

Save it securely. You cannot retrieve the full key again later.

List keys:

```bash
sudo headscale apikeys list
```

Expire a key by prefix:

```bash
sudo headscale apikeys expire --prefix <PREFIX>
```

BenchPress should store the API key as a password/secret field, not plain text.

---

## 15. REST API usage

Headscale REST API base:

```text
https://headscale.example.com/api/v1
```

Swagger docs are available on a running server:

```text
https://headscale.example.com/swagger
```

Version endpoint:

```bash
curl https://headscale.example.com/version
```

List users:

```bash
curl \
  -H "Authorization: Bearer <HEADSCALE_API_KEY>" \
  https://headscale.example.com/api/v1/user
```

Get one user by name:

```bash
curl \
  -H "Authorization: Bearer <HEADSCALE_API_KEY>" \
  "https://headscale.example.com/api/v1/user?name=benchpress-admin"
```

Register a node by auth ID:

```bash
curl \
  -H "Authorization: Bearer <HEADSCALE_API_KEY>" \
  --json '{"user": "benchpress-admin", "authId": "<AUTH_ID>"}' \
  https://headscale.example.com/api/v1/auth/register
```

BenchPress integration should use the API for:

- user/team mapping
- node listing
- device status
- pre-auth key lifecycle if supported by the target API version
- node deletion/revocation
- route listing/approval where needed

Where API coverage is incomplete or version-specific, BenchPress can call the Headscale CLI as a controlled adapter, but API-first is preferred.

---

## 16. gRPC/CLI remote control

Headscale also supports gRPC remote control.

Minimal CLI config:

```yaml
cli:
  address: headscale.example.com:50443
  api_key: <HEADSCALE_API_KEY>
```

Or environment variables:

```bash
export HEADSCALE_CLI_ADDRESS="headscale.example.com:50443"
export HEADSCALE_CLI_API_KEY="<HEADSCALE_API_KEY>"
```

Test:

```bash
headscale nodes list
```

For production, keep gRPC TLS enabled. Do not use `grpc_allow_insecure: true` except in local-only tests.

---

## 17. BenchPress integration checklist

### Settings to add later

Possible BenchPress Settings fields:

- `headscale_enabled`
- `headscale_server_url`
- `headscale_api_key` as password/secret
- `headscale_base_domain`
- `headscale_default_user`
- `headscale_auth_key_ttl`
- `headscale_mode`: `subnet_router`, `container_node`, or `hybrid`

### Doctor/preflight checks

BenchPress doctor should verify:

- `headscale version` works or REST `/version` works.
- Headscale config is valid.
- API key works.
- Required DNS is configured.
- TLS certificate is valid.
- `/api/v1/user` returns successfully.
- Pre-auth key creation works.
- Client/node registration path is tested.
- ACL file is valid.
- Cleanup/revocation commands work.

### Security rules

- Never print API keys or pre-auth keys in logs.
- Keep auth keys short-lived by default.
- Prefer per-user or per-bench keys.
- Revoke nodes when a user/device/bench is deleted.
- Avoid broad ACLs in production.
- Do not imply official Tailscale endorsement.

---

## 18. Troubleshooting

### `dns.nameservers.global must be set`

Cause:

- `dns.override_local_dns` is true, but no global nameservers are configured.

Fix:

```yaml
dns:
  override_local_dns: true
  nameservers:
    global:
      - 1.1.1.1
      - 1.0.0.1
```

### `preauthkeys create --user` rejects username

In Headscale `v0.28.0`, use numeric user ID:

```bash
sudo headscale users list
sudo headscale preauthkeys create --user 1 --expiration 1h
```

### Client cannot log in

Check:

- `server_url` is publicly reachable.
- TLS certificate is valid.
- Tailscale client command uses the same URL as `server_url`.
- Pre-auth key is not expired.
- Headscale service is running.

### API returns unauthorized

Check:

- `Authorization: Bearer <API_KEY>` header is present.
- API key has not expired.
- You did not copy only the API key prefix.

---

## 19. Recommended BenchPress next step

Before building full Headscale support, complete a focused spike:

1. Install Headscale using this guide on a test host.
2. Create one BenchPress admin user mapping.
3. Register one developer device.
4. Expose one bench private service.
5. Test SSH/code-server access.
6. Revoke the device.
7. Delete the bench and confirm cleanup.
8. Decide final architecture: subnet router vs container node vs hybrid.

This keeps the Headscale decision product-safe while Phase 1 public browser access moves forward independently.
