#!/bin/bash

echo "[*] Starting Redis..."
redis-server --daemonize yes

echo "[*] Starting SSH..."
mkdir -p /var/run/sshd
service ssh start || /usr/sbin/sshd

if [ -f "/etc/wireguard/wg0.conf" ]; then
    echo "[*] Starting WireGuard VPN..."
    wg-quick up wg0 || true
fi

echo "[*] Services ready."
exec tail -f /dev/null
