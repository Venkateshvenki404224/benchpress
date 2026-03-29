#!/bin/bash

echo "[*] Starting MariaDB..."
mkdir -p /run/mysqld && chown mysql:mysql /run/mysqld

# Reinitialize data directory if volume was cleared (edge case)
if [ ! -d "/var/lib/mysql/mysql" ]; then
    echo "[*] Initializing MariaDB data directory..."
    mysql_install_db --user=mysql --datadir=/var/lib/mysql
fi

service mariadb start || mysqld_safe &
sleep 3

# Set root password on first boot (no-op on restart — fails silently if password already set)
if mariadb -u root -e "SELECT 1" &>/dev/null; then
    echo "[*] Setting MariaDB root password..."
    mariadb -u root -e "ALTER USER 'root'@'localhost' IDENTIFIED BY 'frappe'; FLUSH PRIVILEGES;"
fi

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
