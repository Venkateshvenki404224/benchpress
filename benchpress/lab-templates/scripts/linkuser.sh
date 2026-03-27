#!/bin/bash
# linkuser.sh — User provisioning for BenchPress containers
# Args: USERNAME EMAIL LAB_NAME WG_IP SSH_PASSWORD BENCH_NAME BASE_DOMAIN MOUNT_TARGET

set -e

USERNAME="$1"
EMAIL="$2"
LAB_NAME="$3"
WG_IP="$4"
SSH_PASSWORD="$5"
BENCH_NAME="$6"
BASE_DOMAIN="$7"
MOUNT_TARGET="${8:-/home/frappe}"

if [ -z "$USERNAME" ] || [ -z "$SSH_PASSWORD" ]; then
    echo "[error] USERNAME and SSH_PASSWORD are required"
    exit 1
fi

echo "[*] Provisioning user: $USERNAME for bench: $BENCH_NAME"

if id "$USERNAME" &>/dev/null; then
    echo "[*] User $USERNAME already exists, skipping creation"
else
    echo "[*] Creating user $USERNAME..."
    adduser --disabled-password --gecos "" --force-badname "$USERNAME"
fi

usermod -aG sudo "$USERNAME"
getent group frappe &>/dev/null && usermod -aG frappe "$USERNAME"

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

echo "[*] Setting up home directory..."
mkdir -p "/home/$USERNAME"
cp -n /etc/skel/.bashrc "/home/$USERNAME/.bashrc" 2>/dev/null || true
cp -n /etc/skel/.profile "/home/$USERNAME/.profile" 2>/dev/null || true
cp -n /etc/skel/.bash_logout "/home/$USERNAME/.bash_logout" 2>/dev/null || true

if ! grep -q "frappe-bench" "/home/$USERNAME/.bashrc" 2>/dev/null; then
    # Find node binary path from nvm or system
    NODE_DIR=$(dirname "$(find /home/frappe/.nvm -name node -type f 2>/dev/null | head -1)" 2>/dev/null || echo "")
    YARN_DIR=$(dirname "$(find /home/frappe/.nvm -name yarn -type f 2>/dev/null | head -1)" 2>/dev/null || echo "")

    cat >> "/home/$USERNAME/.bashrc" << BASHEOF

export NVM_DIR="/home/frappe/.nvm"
[ -s "\$NVM_DIR/nvm.sh" ] && . "\$NVM_DIR/nvm.sh"
export PATH="\$PATH:/home/frappe/frappe-bench/env/bin${NODE_DIR:+:$NODE_DIR}${YARN_DIR:+:$YARN_DIR}"
if [ -d "/home/frappe/frappe-bench" ]; then
    cd /home/frappe/frappe-bench
fi
BASHEOF
fi

chown -R "$USERNAME:$USERNAME" "/home/$USERNAME"

BENCH_DIR="$MOUNT_TARGET/frappe-bench"
if [ -d "$BENCH_DIR" ]; then
    echo "[*] Setting bench directory ownership to $USERNAME..."
    chown -R "$USERNAME:$USERNAME" "$BENCH_DIR"
fi

[ -d "$MOUNT_TARGET" ] && chown "$USERNAME:$USERNAME" "$MOUNT_TARGET"


cat > "/.benchpress_config" << CFGEOF
{
    "username": "$USERNAME",
    "email": "$EMAIL",
    "lab_name": "$LAB_NAME",
    "bench_name": "$BENCH_NAME",
    "wg_ip": "$WG_IP",
    "base_domain": "$BASE_DOMAIN",
    "mount_target": "$MOUNT_TARGET",
    "provisioned_at": "$(date -Iseconds)"
}
CFGEOF

echo "[*] User provisioning complete for $USERNAME"
