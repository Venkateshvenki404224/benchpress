#!/bin/bash
set -euo pipefail

USERNAME="$1"
EMAIL="$2"
LAB_NAME="$3"
WG_IP="$4"
BENCH_NAME="$5"
BASE_DOMAIN="$6"
LOGIN_SHELL="${7:-/bin/bash}"
[ -x "$LOGIN_SHELL" ] || LOGIN_SHELL=/bin/bash
USER_HOME="/home/$USERNAME"

echo "[*] Setting up $USERNAME on $BENCH_NAME"

userdel --remove ubuntu 2>/dev/null || true
useradd --uid 1000 --create-home --shell "$LOGIN_SHELL" --groups sudo "$USERNAME"
install -m 0440 /dev/stdin "/etc/sudoers.d/$USERNAME" <<< "$USERNAME ALL=(ALL:ALL) NOPASSWD: ALL"

ln -sfn /opt/frappe-bench "$USER_HOME/frappe-bench"
ln -sfn /opt/nvm-seed "$USER_HOME/.nvm"
cat >> "$USER_HOME/.bashrc" <<'RC'
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
cd ~/frappe-bench 2>/dev/null || true
RC
mkdir -p "$USER_HOME/.config/code-server"
chown -R "$USERNAME:$USERNAME" "$USER_HOME"

for var in CI FRAPPE_BIND_ADDR; do
    if [ -n "${!var:-}" ]; then echo "$var=${!var}" >> /etc/environment; fi
done

export USERNAME EMAIL LAB_NAME WG_IP BENCH_NAME BASE_DOMAIN USER_HOME
python3 - <<'PY'
import json, os
from datetime import datetime

keys = ("username", "email", "lab_name", "bench_name", "wg_ip", "base_domain")
config = {key: os.environ[key.upper()] for key in keys}
config["mount_target"] = os.environ["USER_HOME"]
config["provisioned_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
with open("/.benchpress_config", "w") as f:
    json.dump(config, f, indent=4)
PY

echo "[*] $USERNAME is ready"
