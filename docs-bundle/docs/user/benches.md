---
title: Work on your own bench
description: Prepare a Frappe develop bench, log in over SSH with your own key,
  create a database, make a site with bench new-site, and serve it with bench
  start on your VPN address.
lastModified: "2026-09-27T09:24:08-04:00"
lastAuthor: Venkatesh
---
# Work on your own bench

A bench from the **Benches** page is an Ubuntu box with a Frappe develop bench
at `~/frappe-bench`. It has no site. You make the sites yourself, on databases
that the dashboard creates for you.

**Who this is for.** A Frappe developer who wants a bench they manage like their
own machine: SSH, root through `sudo`, and code-server.

**Before you start.** Your laptop must be on the VPN. See
[Register a VPN device](/docs/user/vpn-devices). You also need an SSH key
pair on your laptop, for example `~/.ssh/id_ed25519` and `~/.ssh/id_ed25519.pub`.

## Prepare the bench

1. Open the menu under your name at the top of the sidebar.
2. Choose **Settings**.
3. In **SSH keys**, press **Add SSH key**.
4. Paste the contents of `~/.ssh/id_ed25519.pub`.
5. Press **Add key**.
6. Open **Benches** in the sidebar.
7. Press **Prepare bench** on the **Frappe develop bench** card.

Settings shows each saved key as its fingerprint. Run
`ssh-keygen -lf ~/.ssh/id_ed25519.pub` on your laptop to see the same fingerprint.

To remove a key, press **Remove** on its row in **SSH keys**. Press **Remove**
again in the confirm dialog. A bench accepts the key until the bench deploys again.

The deploy dialog shows each step. When the image is already built, the bench
is ready in about a minute. The first launch builds the image and takes about
30 minutes.

## Log in over SSH

1. Open the bench from **Your benches** on the **Benches** page.
2. Copy the **SSH** line from **Connection details**. It reads
   `ssh <user>@<wg-ip>`.
3. Run that line in a terminal on your laptop.

The login uses your key. A password login is refused. Run `sudo -i` for a root
shell.

## Create a database

1. Press **Create database** on the **Databases** card of the bench page.
2. Copy the command that the card shows.

The card shows the database name, its user, the password and the full command.
The command has this shape:

```bash
bench new-site <site> --set-default --no-setup-db --db-host benchpress-mariadb \
  --db-name <db> --db-user <user> --db-password <password>
```

The database user has all privileges on its own database and on no other
database. It cannot create databases or users.

To see the password and the command again, press **Show password** on the
database row.

A bench holds at most five databases. An operator changes this limit with
**Databases per self-managed bench** in **BenchPress Settings**.

## Make a site and serve it

1. Paste the command in your SSH session.
2. Type an administrator password for the new site when `bench new-site` asks.
3. Run `bench start` in `~/frappe-bench`.
4. Open `http://<wg-ip>:8000` in a browser on your laptop.

`--set-default` makes the new site the bench's default site. `bench start` then
serves it on the bench's VPN address, whatever host name the request carries.

Each command sets its own site as the default. After a second site, the VPN
address serves the newer one. To serve an earlier site again, run
`bench use <site>` and restart `bench start`.

To check the site from a terminal, run this command on your laptop:

```bash
curl http://<wg-ip>:8000/api/method/ping
```

The reply is `{"message":"pong"}`.

## What happens to a database later

|Action|The database|The site folder in `~/frappe-bench/sites`|
|--|--|--|
|Stop and start the bench|Kept|Kept|
|Redeploy the bench|Kept|Gone, because the redeploy replaces the container|
|The stopped bench is reaped after `reap_after_days`|Dropped, with its user|Gone|
|Delete the bench|Dropped, with its user|Gone|

Delete a bench only when you no longer need its sites. BenchPress cannot bring
back a dropped database.
