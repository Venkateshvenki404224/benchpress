#!/bin/bash

echo "[*] Starting MariaDB..."
service mariadb start

echo "[*] Starting Redis..."
redis-server --daemonize yes

echo "[*] Starting SSH..."
service ssh start

echo "[*] Checking WireGuard..."
if [ -f /etc/wireguard/wg0.conf ]; then
    wg-quick up wg0
    echo "[*] WireGuard interface up."
fi

echo "[*] BenchPress container ready."
dumb-init tail -f /dev/null
