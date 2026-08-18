# Lab Access Acceptance Run

A numbered checklist to repeat after any change to the deploy pipeline, the lab image, or the access
surface. It answers one question: **can a user reach the lab they were just told is ready?**

Run it against a lab deployed from a template, with a WireGuard tunnel up on the machine you run it
from. Record the result of every step — a step that was not exercised is reported as not exercised, never
as a pass.

Shell access in this product is SSH over WireGuard, or the terminal inside code-server. There is no web
terminal; see [ARCHITECTURE.md](../ARCHITECTURE.md) § Shell Access.

---

## 0. Prerequisites

| Need | How |
|------|-----|
| A running lab | Deploy one from the Labs page, or reuse one whose bench is `Running` |
| A registered device | Devices → **Add device**, import the `.conf`, bring the tunnel up |
| The bench's addresses and secrets | Lab detail → **Connection details** (secrets behind **Reveal secrets**) |

Throughout, `<wg_ip>` is the bench's WireGuard IP, `<user>` its SSH username and `<site>` its site name —
all three are on that card.

---

## 1. The deploy is genuinely green

Lab detail → **Deploy log**. All eleven steps show `success` in the stepper, and the raw log holds no
`[warn]` line. A build that ran inside the deploy has its own tab; a warning there is a real finding
even when the deploy is green (`_ensure_assets` degrades to a warning on purpose — stale bundles still
serve, a killed deploy does not).

> A deploy of a cached image lands in ~30 s. Minutes mean the image cache missed.

## 2. The site loads and the admin password works

Click **Open site**. The site answers on `http://<wg_ip>:8000`, and `administrator` with the **Admin
password** from Connection details logs in.

Headless equivalent, from a machine on the tunnel:

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://<wg_ip>:8000/          # 200
curl -s -X POST http://<wg_ip>:8000/api/method/login \
     -d "usr=Administrator&pwd=<admin_password>"                        # {"message":"Logged In"}
```

## 3. The IDE opens, with the password in hand

Click **Open VS Code**. Two things must happen:

1. A new tab opens `http://<wg_ip>:8080/`.
2. A **code-server password** dialog appears on the lab page with the password and a copy button. The
   password is never in the URL — a query parameter would land in browser history, in the container's
   access log and in every proxy between.

Paste it into code-server. The window opens on the bench directory: the file tree shows `apps/`,
`sites/`, `env/`, and the URL carries `?folder=/home/<user>/frappe-bench`.

Headless equivalent:

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://<wg_ip>:8080/          # 302 (login)
COOKIE=$(curl -s -i -X POST http://<wg_ip>:8080/login \
         -d "password=<code_server_password>&base=." |
         grep -i '^set-cookie' | sed 's/Set-Cookie: //;s/;.*//')
curl -s -i -H "Cookie: $COOKIE" http://<wg_ip>:8080/ | grep -i '^location'
# Location: ./?folder=/home/<user>/frappe-bench
```

If code-server does not answer at all, `benchpress.api.restart_code_server` relaunches it without a
redeploy. It has no button yet — wire one into the overflow menu the day this step starts needing it.

## 4. The integrated terminal is a real bench shell

Open a terminal inside code-server and run:

```bash
whoami                                  # the lab's ssh_username, not frappe
pwd                                     # /home/<user>/frappe-bench
bench --site <site> list-apps           # the resolved app list
bench version
```

All four must work with no `sudo` and no PATH fix — `linkuser.sh` appends the nvm node path and
`frappe-bench/env/bin` to the user's `.bashrc`, and points the shell at the bench directory. A failure
here is that block.

> `/home/<user>` is a symlink to `/home/frappe`, so a tool that resolves symlinks may print
> `/home/frappe/frappe-bench`. Same directory.

## 5. SSH does the same from your own machine

Copy the SSH line from Connection details and run it with the SSH password:

```bash
ssh <user>@<wg_ip>
# whoami → <user>, pwd → /home/<user>/frappe-bench, bench --site <site> list-apps works
```

**A one-shot command is not a login shell.** `ssh <user>@<wg_ip> "bench --site <site> list-apps"` runs a
non-interactive shell, and Debian's `.bashrc` returns before the bench block for those — so it starts in
the home directory and `bench` reports *"Command not being executed in bench directory"*. Name the
directory when scripting:

```bash
ssh <user>@<wg_ip> "cd frappe-bench && bench --site <site> list-apps"
```

## 6. Off the tunnel, the UI is honest

Disconnect the tunnel and reload nothing — return to the browser tab.

- **Open site** and **Open VS Code** are disabled and say why ("Register this device on the VPN…").
- Each site row reads `Unreachable` with its own reason, distinct from a stopped container's.
- Reconnecting the tunnel re-enables them on the next focus of the tab — the VPN status is re-read on
  window focus and on page mount, so no hard reload is needed.
- Nothing spins forever.

## 7. With the bench stopped, nothing offers a dead address

Stop the bench from the overflow menu.

- The **Open VS Code** button is gone (`code_server_url` is cleared, and the button follows it).
- The site row reads `Inactive`, its Open button is disabled and says the container is stopped.
- The primary action is **Deploy**, not **Open site**.

Deploy again to bring it back — there is no start-a-stopped-instance path yet
([#127](https://github.com/Venkateshvenki404224/benchpress/issues/127)).

## 8. A failed deploy names its own cause

Point a Lab App row at a branch that does not exist and deploy.

- The banner names the **image build** failure, not the deploy's log tail.
- Its button opens the **Build log** tab, and the build log holds the git error.

---

## What to record

For each numbered step: pass, fail, or not exercised — with the reason for the last one. A run that
skipped the tunnel is a run that did not test the tunnel.

Two known intermittents, neither a defect of the step they break:

- `wg-quick up wg0` can report *"wg0 already exists"* at step 5 when the container's own entrypoint won
  the race. Retry the deploy.
- `codeload.github.com` rate-limits this host in bursts. A 429 during an image build is retryable.

## When the public hostname lands

[#129](https://github.com/Venkateshvenki404224/benchpress/issues/129) gives every instance a public
`<instance-id>.benchpress.cloud` name, and [#130](https://github.com/Venkateshvenki404224/benchpress/issues/130)
points the open actions at it. This checklist is then re-run with `<wg_ip>` replaced by that hostname and
step 6 inverted — off the tunnel becomes the normal case, which is
[#133](https://github.com/Venkateshvenki404224/benchpress/issues/133).

Before that lands, fix the exposure it uncovers: code-server binds `0.0.0.0:8080` with `cert: false`, so
it is plaintext HTTP on every interface of the container, with its password as the only control. That is
acceptable while WireGuard is the sole ingress and unacceptable the moment a public hostname points at it.
