#!/bin/bash

echo "[*] Starting Redis..."
redis-server --daemonize yes

echo "[*] Starting SSH..."
mkdir -p /var/run/sshd
service ssh start || /usr/sbin/sshd

if [ -f /.benchpress_config ]; then
    TARGET_USER=$(python3 -c "import json; print(json.load(open('/.benchpress_config')).get('username',''))" 2>/dev/null || echo "")
    if [ -n "$TARGET_USER" ] && [ -f "/home/$TARGET_USER/.config/code-server/config.yaml" ]; then
        echo "[*] Starting code-server in detached screen session for $TARGET_USER..."
        sudo -u "$TARGET_USER" screen -d -m -S codeserver \
            code-server "/home/$TARGET_USER/frappe-bench" || true
    fi
fi

if [ -f "/etc/wireguard/wg0.conf" ]; then
    echo "[*] Starting WireGuard VPN..."
    wg-quick up wg0 || true
fi

echo "[*] Services ready."
exec tail -f /dev/null
