#!/bin/bash
set -euo pipefail

FRAPPE_BRANCH="${1:-develop}"
BENCH_PATH=/opt/frappe-bench
BENCH_OWNER=ubuntu
PYTHON=python3.14

add-apt-repository -y ppa:deadsnakes/ppa
apt-get update
apt-get install -y --no-install-recommends \
    "$PYTHON" "$PYTHON-venv" "$PYTHON-dev" redis-server mariadb-client pkg-config libmariadb-dev
rm -rf /var/lib/apt/lists/*

NODE_PATH_DIR=$(dirname "$(ls -d /opt/nvm-seed/versions/node/*/bin/node | sort -V | tail -1)")
PATH="$NODE_PATH_DIR:$PATH" npm install -g yarn
PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin pipx install frappe-bench
ln -sf /opt/pipx/venvs/frappe-bench/bin/uv /opt/pipx/venvs/frappe-bench/bin/uvx /usr/local/bin/

install -d -o "$BENCH_OWNER" -g "$BENCH_OWNER" "$BENCH_PATH"
sudo -u "$BENCH_OWNER" env PATH="$NODE_PATH_DIR:/usr/local/bin:$PATH" \
    bench init "$BENCH_PATH" --ignore-exist --no-backups --verbose \
        --frappe-branch "$FRAPPE_BRANCH" --python "/usr/bin/$PYTHON"

rm -rf "/home/$BENCH_OWNER/.cache"
chown -R 1000:1000 /opt/nvm-seed
