---
title: Use code-server
description: Open the browser VS Code session on a bench, find its password,
  hand the session to a teammate, and restart it when it stops answering.
lastModified: "2026-08-28T11:17:35Z"
lastAuthor: Venkatesh
---
# Use code-server

Every bench whose lab enables it runs code-server, which is VS Code in a
browser tab. This page opens it, logs in, and shares the session.

**Who this is for.** Anybody with a running bench who would rather not install
an SSH client or a remote-development extension.

**Before you start.** The bench must read `Running`, and the lab must have
code-server switched on. Look at the chips under the lab title. A lab with the
IDE shows a `code-server` chip and the header offers **Open VS Code**.

## Steps

1. Press **Open VS Code** in the lab header. The IDE opens in a new tab and
   BenchPress shows the password for it on the page you left.

   ![The Helpdesk sandbox lab page at 1280 by 800 pixels with a small dialog over it, headed code-server password. The dialog text reads that code-server asks for this password and that every redeploy replaces it. Below the text a read-only field holds a random twenty-character password in plain text, with a copy button beside it. The lab header behind the dialog carries the chips version-16, 2 GB, 2 vCPU, code-server and SSH, and the buttons Open VS Code and Open site.](../images/user/code-server/01-password-dialog.png)

   The password is shown, not masked. The dialog exists so the password can be
   read beside the login form that is now asking for it.

   The password is never put in the address. A query parameter would land in
   browser history, in the container access log, and in every proxy between
   the two.

2. Press the copy button in the dialog.

3. Switch to the new tab and paste the password into code-server's own login
   page.

   ![The code-server login page filling the browser window at 1280 by 800 pixels. A white card on a pale background is headed Welcome to code-server. The line under it reads, Please log in below. Check the config file at slash home slash intern slash dot config slash code-server slash config dot yaml for the password. A single empty field labeled PASSWORD sits below, with a blue SUBMIT button to its right.](../images/user/code-server/02-login.png)

   This page is code-server's, not BenchPress's. It points at
   `/home/<username>/.config/code-server/config.yaml` because that is where
   code-server keeps its own copy. Use the password BenchPress gave you. It is
   the same one.

4. Press **SUBMIT**. The bench opens as a workspace.

   ![The code-server workspace in a browser at 1280 by 800 pixels, showing VS Code for the Web with a light theme. The Explorer on the left is rooted at FRAPPE-BENCH and expands apps into crm, erpnext, frappe, helpdesk, hrms, lms, payments and telephony, followed by config, env, logs and sites, then patches.txt and Procfile. The editor area holds the Get Started with VS Code for the Web walkthrough tab. The status bar at the foot reports 0 errors and 0 warnings.](../images/user/code-server/03-workspace.png)

   The workspace opens at `/home/frappe/frappe-bench`. The `apps` folder holds
   one directory per app the lab installed. In the frame that is `crm`,
   `erpnext`, `frappe`, `helpdesk`, `hrms`, `lms`, `payments` and `telephony`.

   `sites` holds the site data, `logs` holds the bench logs, and `Procfile`
   lists the processes the bench runs.

5. Use the built-in terminal for bench commands. The terminal is a shell in
   the same container SSH would give you, so nothing extra is needed.

## Share a session with a teammate

The IDE address is a public HTTPS hostname. Send a teammate the address and
the password and they open the same workspace, from anywhere, with no VPN and
no BenchPress account.

1. Copy the **code-server** address from **Connection details**.
2. Copy the **code-server password** from the same card.
3. Send both.

**Anybody holding those two strings has a shell on the bench.** The password
is the only thing in front of it. Share a session for as long as the work
takes, then redeploy the bench, which replaces the password.

## Verify

* The IDE tab shows the file tree rooted at `frappe-bench`.
* The terminal answers `whoami` with your bench username, not `root`.
* **Connection details** lists a `code-server` row with an `https://ide-…`
  address.

## Troubleshooting

|Symptom|Cause|Fix|
|--|--|--|
|No **Open VS Code** button|The lab has code-server switched off|Ask an admin to enable it on the lab, then redeploy|
|`Bench must be running to access code-server`|The bench is stopped or still deploying|Start the bench and try again|
|`Code-server is not enabled for this lab`|The deploy stored no IDE address|Redeploy the bench|
|The password dialog says the request failed|The bench stopped between the click and the call|Reload the lab page and check the container status|
|The login page rejects the password|The bench was redeployed after the password was copied|Reopen **Open VS Code** for the current password|
|The IDE tab never loads|The IDE process is not answering|Restart it, or redeploy the bench|
|The IDE loads but the terminal is empty|The workspace opened before the container settled|Reload the tab|

## Reference

### The two passwords are different

|Password|Opens|Where it is shown|
|--|--|--|
|code-server password|the IDE login page|the dialog, and **Connection details**|
|SSH password|an SSH session|**Connection details** only|
|Admin password|`Administrator` on the Frappe site|**Connection details** only|

All three are generated per deploy and all three are replaced by a redeploy.

### Restarting code-server

BenchPress has an endpoint that restarts the IDE process without touching the
bench. It runs `restart.sh` inside the container as `root` and leaves the
container, the site and the database alone.

`restart_code_server` has no button in the app today. Until it gets one,
restart the IDE from the API:

```bash
curl -X POST https://<your-server>/api/method/benchpress.api.restart_code_server \
     -H "Authorization: token <api_key>:<api_secret>" \
     -d "bench_name=<bench id>"
```

The endpoint refuses a bench that is not `Running` or has no container. A
redeploy also restarts the IDE, at the cost of the container's writable layer.

### What the IDE can reach

code-server runs inside the bench container as your bench user. It sees the
bench filesystem and nothing else on the host. It is not a route into other
benches.

## Related

* [Connect over SSH and the VPN](/docs/user/connect-ssh-vpn) — the card that holds the IDE address and its password.
* [Start, stop and redeploy](/docs/user/lifecycle) — which action replaces the IDE password.
* [Read a lab page](/docs/user/lab-detail) — the chips that say whether a lab has an IDE.
