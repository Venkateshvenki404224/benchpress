#!/bin/bash
set -e

# The caller (deploy_manager) already sets workdir to the bench dir; this cd is a fallback.
cd /home/frappe/frappe-bench || true

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

# Create localhost alias so port-forwarded access works without matching Host header
cd sites
for alias in localhost 0.0.0.0; do
    [ ! -e "$alias" ] && ln -sf "${SITE_NAME}" "$alias"
done
cd ..

echo "[*] Site ${SITE_NAME} ready."
