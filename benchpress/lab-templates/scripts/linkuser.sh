#!/bin/bash
# linkuser.sh — User provisioning for BenchPress containers
# Renames the 'frappe' user to the dynamic username instead of creating a new one.
# Args: USERNAME EMAIL LAB_NAME WG_IP SSH_PASSWORD BENCH_NAME BASE_DOMAIN MOUNT_TARGET ADMIN_PASSWORD

set -e

USERNAME="$1"
EMAIL="$2"
LAB_NAME="$3"
WG_IP="$4"
SSH_PASSWORD="$5"
BENCH_NAME="$6"
BASE_DOMAIN="$7"
MOUNT_TARGET="${8:-/home/frappe}"
ADMIN_PASSWORD="$9"

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

usermod --shell /bin/bash "$USERNAME"
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

chown -R "$USERNAME:$USERNAME" /home/frappe

BENCH_DIR="/home/$USERNAME/frappe-bench"

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
