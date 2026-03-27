#!/bin/bash
set -e

SITE_NAME="$1"
ADMIN_PASSWORD="$2"
APPS_JSON="$3"

echo "[create-site] Starting MariaDB..."
service mariadb start
sleep 3

echo "[create-site] Setting MariaDB root password..."
mariadb -u root -e "ALTER USER 'root'@'localhost' IDENTIFIED BY 'frappe'; FLUSH PRIVILEGES;"

echo "[create-site] Starting Redis..."
redis-server --daemonize yes

# Build --install-app flags
INSTALL_FLAGS=""
if [ -n "$APPS_JSON" ] && [ "$APPS_JSON" != "[]" ]; then
    INSTALL_FLAGS=$(echo "$APPS_JSON" | python3 -c "
import sys, json
apps = json.load(sys.stdin)
flags = []
for app in apps:
    if app.get('app_name') == 'frappe':
        continue
    flags.append(f'--install-app {app[\"app_name\"]}')
print(' '.join(flags))
")
fi

echo "[create-site] Creating site ${SITE_NAME} with flags: ${INSTALL_FLAGS}"
su frappe -c "cd /home/frappe/frappe-bench && bench new-site ${SITE_NAME} \
    --mariadb-user-host-login-scope='%' \
    --admin-password=${ADMIN_PASSWORD} \
    --db-root-username=root \
    --db-root-password=frappe \
    --set-default \
    ${INSTALL_FLAGS}"

echo "[create-site] Building assets..."
su frappe -c "cd /home/frappe/frappe-bench && bench build"

echo "[create-site] Stopping services..."
service mariadb stop || mysqladmin -u root -pfrappe shutdown || true
redis-cli shutdown || true
sleep 2

echo "[create-site] Done."
