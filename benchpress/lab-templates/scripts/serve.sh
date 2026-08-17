#!/bin/bash
# Serve the lab's site, replacing any server already running.
#
# `CI=1` is the security-relevant part. Without it `bench serve` hands Werkzeug `use_debugger`
# and `use_evalex` (frappe/app.py), which mounts the debugger's `/console` Python evaluator on
# 0.0.0.0:8000 — and lab containers share one bridge and one WireGuard pool, so that console is
# reachable by every other tenant.
#
# The account comes from /.benchpress_config, which linkuser.sh writes as root, and never from
# the ownership of the bench directory: that directory lives in the tenant's own volume, so a
# tenant who chowned it could otherwise choose the account this root-invoked script drops to.
#
# Must run after linkuser.sh: that renames the bench user, and `usermod --login` refuses to
# rename a user that owns a running process.
set -euo pipefail

CONFIG=/.benchpress_config
BENCH_DIR=/home/frappe/frappe-bench
SESSION=benchweb
BENCH_USER="${1:-}"
PORT="${2:-8000}"

if [ -z "$BENCH_USER" ]; then
    [ -f "$CONFIG" ] || { echo "[!] $CONFIG missing — cannot tell which account owns the bench."; exit 1; }
    BENCH_USER=$(python3 -c "import json; print(json.load(open('$CONFIG')).get('username',''))")
fi
[ -n "$BENCH_USER" ] || { echo "[!] No bench user recorded."; exit 1; }
[[ "$PORT" =~ ^[0-9]+$ ]] || { echo "[!] Port must be a number, got '$PORT'."; exit 1; }

sudo -u "$BENCH_USER" screen -X -S "$SESSION" quit || true
sudo -u "$BENCH_USER" screen -d -m -S "$SESSION" \
    bash -lc "cd '$BENCH_DIR' && CI=1 bench serve --port '$PORT' --noreload"
