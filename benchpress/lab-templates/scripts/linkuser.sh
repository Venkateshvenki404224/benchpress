#!/bin/bash
# linkuser.sh — User provisioning for BenchPress containers
# Renames the 'frappe' user to the dynamic username instead of creating a new one.
# Args: USERNAME EMAIL LAB_NAME WG_IP BENCH_NAME BASE_DOMAIN LOGIN_SHELL
# SSH_PASSWORD comes from the environment, not from argv: Docker publishes an exec's
# command line into its event stream and does not publish its environment.

set -e

USERNAME="$1"
EMAIL="$2"
LAB_NAME="$3"
WG_IP="$4"
BENCH_NAME="$5"
BASE_DOMAIN="$6"
LOGIN_SHELL="${7:-/bin/bash}"

if [ -z "$USERNAME" ] || [ -z "$SSH_PASSWORD" ]; then
    echo "[error] USERNAME and SSH_PASSWORD are required"
    exit 1
fi

echo "[*] Provisioning user: $USERNAME for bench: $BENCH_NAME"

# Rename frappe group and user to the dynamic username
echo "[*] Renaming frappe user to $USERNAME..."
groupmod -n "$USERNAME" frappe
usermod --login "$USERNAME" --home "/home/$USERNAME" frappe
ln -sfn /home/frappe "/home/$USERNAME"

# Honor the lab's configured login shell; fall back to bash if it is missing
# or not executable in this image (also guards against a malformed value).
if [ ! -x "$LOGIN_SHELL" ]; then
    echo "[warn] login shell '$LOGIN_SHELL' not found or not executable; falling back to /bin/bash"
    LOGIN_SHELL="/bin/bash"
fi
usermod --shell "$LOGIN_SHELL" "$USERNAME"
usermod -aG sudo "$USERNAME"

echo "[*] Setting SSH password..."
echo "$USERNAME:$SSH_PASSWORD" | chpasswd

echo "[*] Configuring sudo permissions..."
cat > "/etc/sudoers.d/$USERNAME" << SUDOEOF
$USERNAME ALL=(ALL:ALL) NOPASSWD: /usr/local/bin/bench
$USERNAME ALL=(ALL:ALL) NOPASSWD: /usr/bin/supervisord
$USERNAME ALL=(ALL:ALL) NOPASSWD: /usr/bin/supervisorctl
$USERNAME ALL=(ALL:ALL) NOPASSWD: /usr/sbin/service
$USERNAME ALL=(ALL:ALL) NOPASSWD: /home/$USERNAME/init.sh
SUDOEOF
chmod 0440 "/etc/sudoers.d/$USERNAME"

# Fix NVM and bench paths in bashrc
if ! grep -q "frappe-bench" "/home/$USERNAME/.bashrc" 2>/dev/null; then
    NODE_DIR=$(dirname "$(find /home/$USERNAME/.nvm -name node -type f 2>/dev/null | head -1)" 2>/dev/null || echo "")
    YARN_DIR=$(dirname "$(find /home/$USERNAME/.nvm -name yarn -type f 2>/dev/null | head -1)" 2>/dev/null || echo "")

    cat >> "/home/$USERNAME/.bashrc" << BASHEOF

export NVM_DIR="/home/$USERNAME/.nvm"
[ -s "\$NVM_DIR/nvm.sh" ] && . "\$NVM_DIR/nvm.sh"
export PATH="\$PATH:/home/$USERNAME/frappe-bench/env/bin${NODE_DIR:+:$NODE_DIR}${YARN_DIR:+:$YARN_DIR}"
if [ -d "/home/$USERNAME/frappe-bench" ]; then
    cd /home/$USERNAME/frappe-bench
fi
BASHEOF
fi

# No chown needed: the rename keeps uid 1000, which already owns every file.

cat > "/.benchpress_config" << CFGEOF
{
    "username": "$USERNAME",
    "email": "$EMAIL",
    "lab_name": "$LAB_NAME",
    "bench_name": "$BENCH_NAME",
    "wg_ip": "$WG_IP",
    "base_domain": "$BASE_DOMAIN",
    "mount_target": "/home/$USERNAME",
    "provisioned_at": "$(date -Iseconds)"
}
CFGEOF

echo "[*] User provisioning complete for $USERNAME"
