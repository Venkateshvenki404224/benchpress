#!/bin/bash
# Serve the lab's site on port 8000, replacing any server already running.
#
# The container's entrypoint cannot do this on first boot: the site is created by
# the deploy, minutes after the container starts. So the deploy calls this once
# the site exists, and entry.sh calls it on every later start — which is what
# makes a restarted instance answer again without a redeploy.
#
# The bench user is read from the bench directory rather than named, because
# linkuser.sh *renames* `frappe` to the lab owner's username: this script runs
# both before that rename (never — see below) and long after it, and a hardcoded
# name is wrong on one side of it. Two consequences worth keeping in mind:
# `usermod --login` refuses to rename a user that owns a running process, so the
# deploy must call this only after linkuser.sh has run.
#
# `--noreload` on purpose: the reloader forks a watcher over the whole bench,
# which is wasted work in a lab whose code is edited through code-server and
# restarted from the UI.
set -e

BENCH_DIR=/home/frappe/frappe-bench
PORT="${1:-8000}"
SESSION=benchweb

BENCH_USER=$(stat -c %U "$BENCH_DIR")

sudo -u "$BENCH_USER" screen -X -S "$SESSION" quit || true
sudo -u "$BENCH_USER" screen -d -m -S "$SESSION" \
    bash -lc "cd $BENCH_DIR && bench serve --port $PORT --noreload"
