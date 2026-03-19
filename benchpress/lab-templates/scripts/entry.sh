#!/bin/bash

echo "[*] Starting MariaDB..."
mkdir -p /run/mysqld && chown mysql:mysql /run/mysqld
service mariadb start || mysqld_safe &
sleep 3

# Set root password on first boot
if mariadb -u root -e "SELECT 1" &>/dev/null; then
    echo "[*] Setting MariaDB root password..."
    mariadb -u root -e "ALTER USER 'root'@'localhost' IDENTIFIED BY 'frappe'; FLUSH PRIVILEGES;"
fi

echo "[*] Starting Redis..."
redis-server --daemonize yes

echo "[*] Starting SSH..."
mkdir -p /var/run/sshd
service ssh start || /usr/sbin/sshd

echo "[*] Services ready."
exec tail -f /dev/null
