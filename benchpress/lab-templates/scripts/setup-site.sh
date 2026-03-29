#!/bin/bash

cd /home/frappe/frappe-bench

echo "[*] Creating site ${SITE_NAME}..."

bench new-site "${SITE_NAME}" \
    --admin-password "${ADMIN_PASSWORD}" \
    --db-host "${DB_HOST}" \
    --db-name "${DB_NAME}" \
    --mariadb-root-username "${MARIADB_ROOT_USERNAME}" \
    --mariadb-root-password "${MARIADB_ROOT_PASSWORD}" \
    --mariadb-user-host-login-scope='%'

if [ -n "${APPS}" ]; then
    IFS=',' read -ra APP_LIST <<< "${APPS}"
    for app in "${APP_LIST[@]}"; do
        echo "[*] Installing app: ${app}..."
        bench --site "${SITE_NAME}" install-app "${app}"
    done
fi

bench --site "${SITE_NAME}" set-config developer_mode 1
bench use "${SITE_NAME}"

echo "[*] Site ${SITE_NAME} ready."
