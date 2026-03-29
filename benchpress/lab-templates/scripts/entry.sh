#!/bin/bash

echo "[*] Starting Redis..."
sudo redis-server --daemonize yes

echo "[*] Starting SSH..."
sudo mkdir -p /var/run/sshd
sudo service ssh start || sudo /usr/sbin/sshd

if [ -f "/etc/wireguard/wg0.conf" ]; then
    echo "[*] Starting WireGuard VPN..."
    wg-quick up wg0 || true
fi

echo "[*] Services ready."
exec tail -f /dev/null
