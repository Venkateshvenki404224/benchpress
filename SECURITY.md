# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| `develop` (latest) | Yes |
| Older branches | No |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report privately through GitHub Security Advisories:

**[Report a vulnerability](https://github.com/Venkateshvenki404224/benchpress/security/advisories/new)**
— or open the repository's **Security** tab and choose *Report a vulnerability*.

The report stays private between you and the maintainers until a fix ships, and
you are credited on the published advisory unless you ask otherwise.

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Response Timeline

- **Acknowledgment:** Within 48 hours
- **Initial assessment:** Within 5 business days
- **Fix timeline:** Depends on severity, but we aim for patches within 2 weeks for critical issues

## Scope

This policy covers the BenchPress Frappe app, including:
- API endpoints (`benchpress/api.py`)
- Docker container management
- WireGuard VPN configuration (see also the
  [vpn_management](https://github.com/Venkateshvenki404224/vpn_management) repository)
- Frontend authentication and authorization

Out of scope: vulnerabilities in the Frappe Framework itself (report those to
[frappe/frappe](https://github.com/frappe/frappe/security)), and findings that
require an attacker to already hold administrator credentials on the host.

## A note on what BenchPress is

BenchPress provisions **disposable development sandboxes**. Each Lab is a
throwaway Frappe bench, reachable over WireGuard, with credentials shown in the
UI. It is not hardened for production workloads or untrusted tenants, and a
finding that amounts to "a Lab owner can reach their own Lab's data" is expected
behaviour rather than a vulnerability.
