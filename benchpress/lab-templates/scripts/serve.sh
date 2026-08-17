#!/bin/bash
# Serve the lab's site, replacing any server already running.
#
# Must run after linkuser.sh: that renames the bench user, and `usermod --login`
# refuses to rename a user that owns a running process. The user is read from the
# bench directory for the same reason — there is no `frappe` user after the rename.
set -e

BENCH_DIR=/home/frappe/frappe-bench
PORT="${1:-8000}"
SESSION=benchweb

BENCH_USER=$(stat -c %U "$BENCH_DIR")

sudo -u "$BENCH_USER" screen -X -S "$SESSION" quit || true
sudo -u "$BENCH_USER" screen -d -m -S "$SESSION" \
    bash -lc "cd $BENCH_DIR && bench serve --port $PORT --noreload"
