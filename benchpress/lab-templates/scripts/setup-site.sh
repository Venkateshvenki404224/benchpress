#!/bin/bash
set -e

# The caller (deploy_manager) already sets workdir to the bench dir; this cd is a fallback.
cd /home/frappe/frappe-bench || true

# A deploy preserves the data volume on purpose — only a teardown removes it — so a bench
# that has been deployed before already has its site on disk. `bench new-site` refuses that
# outright ("Site ... already exists"), which turned pressing Deploy on an existing instance
# into a failed deploy. The site is adopted instead: nothing here destroys a site, so a
# rebuild from scratch stays an explicit Delete bench (or redeploy), which drops the volume.
if [ -f "sites/${SITE_NAME}/site_config.json" ]; then
    echo "[*] Site ${SITE_NAME} already exists — adopting it."
    # Every deploy mints a fresh admin password and the lab page shows it, so the existing
    # site is moved onto that password rather than leaving the screen describing a
    # credential that does not work.
    bench --site "${SITE_NAME}" set-admin-password "${ADMIN_PASSWORD}"
else
    echo "[*] Creating site ${SITE_NAME}..."
    bench new-site "${SITE_NAME}" \
        --admin-password "${ADMIN_PASSWORD}" \
        --db-host "${DB_HOST}" \
        --db-name "${DB_NAME}" \
        --mariadb-root-username "${MARIADB_ROOT_USERNAME}" \
        --mariadb-root-password "${MARIADB_ROOT_PASSWORD}" \
        --mariadb-user-host-login-scope='%'
fi

if [ -n "${APPS}" ]; then
    # `install-app` errors on an app that is already installed, which the adopt path above
    # makes the normal case, so the site is asked what it already has first.
    INSTALLED=$(bench --site "${SITE_NAME}" list-apps 2>/dev/null | awk '{print $1}')
    IFS=',' read -ra APP_LIST <<< "${APPS}"
    for app in "${APP_LIST[@]}"; do
        if echo "${INSTALLED}" | grep -qx "${app}"; then
            echo "[*] App already installed: ${app}"
        else
            echo "[*] Installing app: ${app}..."
            bench --site "${SITE_NAME}" install-app "${app}"
        fi
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
