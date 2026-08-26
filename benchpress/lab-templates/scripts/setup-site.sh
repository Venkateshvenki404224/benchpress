#!/bin/bash
set -e

# The caller (deploy_manager) already sets workdir to the bench dir; this cd is a fallback.
cd /home/frappe/frappe-bench || true

GOLDEN=/opt/benchpress/golden/site.sql.gz
MANIFEST=/opt/benchpress/golden/manifest.json

# A deploy preserves the data volume, so an instance deployed before already has its
# site. Adopted rather than recreated; nothing here destroys a site.
if [ -f "sites/${SITE_NAME}/site_config.json" ]; then
    echo "[*] Site ${SITE_NAME} already exists — adopting it."
    # The lab page shows the password this run minted, so the site must move onto it. On argv,
    # where any process in the container can read it from /proc/*/cmdline — accepted, because the
    # only readers are the tenant's own processes and the lab page already shows them this
    # password. Moving it to stdin means `getpass` with no controlling terminal, which hangs the
    # deploy if a TTY ever is attached.
    bench --site "${SITE_NAME}" set-admin-password "${ADMIN_PASSWORD}"
# -s rather than -f: a zero-byte dump is a failed copy, and restoring one leaves a site with
# no tables and no error.
elif [ "${USE_GOLDEN:-1}" = "1" ] && [ -s "$GOLDEN" ]; then
    echo "[*] Restoring ${SITE_NAME} from the image's golden dump..."
    bench new-site "${SITE_NAME}" \
        --source-sql "$GOLDEN" \
        --admin-password "${ADMIN_PASSWORD}" \
        --db-host "${DB_HOST}" \
        --db-name "${DB_NAME}" \
        --mariadb-root-username "${MARIADB_ROOT_USERNAME}" \
        --mariadb-root-password "${MARIADB_ROOT_PASSWORD}" \
        --mariadb-user-host-login-scope='%'
    # Every tenant of this lab restores the same bytes, so the dump's own Administrator hash
    # must never be what one of them logs in with.
    bench --site "${SITE_NAME}" set-admin-password "${ADMIN_PASSWORD}"
    RESTORED=1
    echo "[*] Restored from golden dump"
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
    # install-app errors on an already-installed app, which the adopt path makes normal.
    if [ -n "${RESTORED:-}" ]; then
        # The manifest is the dump's own statement of what it carries, and reading it costs a
        # file read against half a second of `bench` startup. An app the lab gained since the
        # golden was baked is still absent from this list, so it is still installed below.
        INSTALLED=$(python3 -c "import json; print('\n'.join(['frappe'] + [a[0] for a in json.load(open('${MANIFEST}'))['apps']]))")
    else
        INSTALLED=$(bench --site "${SITE_NAME}" list-apps 2>/dev/null | awk '{print $1}')
    fi
    IFS=',' read -ra APP_LIST <<< "${APPS}"
    for app in "${APP_LIST[@]}"; do
        # -F: an app name is a literal, not a pattern. A name carrying regex metacharacters
        # would otherwise read as already-installed and the install would be skipped silently.
        if echo "${INSTALLED}" | grep -qxF -- "${app}"; then
            echo "[*] App already installed: ${app}"
        else
            echo "[*] Installing app: ${app}..."
            bench --site "${SITE_NAME}" install-app "${app}"
        fi
    done
fi

# No `set-config developer_mode` and no `bench use` here: the control plane writes both keys
# into common_site_config.json before this runs, and each was half a second of `bench` startup.

# Create localhost alias so port-forwarded access works without matching Host header
cd sites
for alias in localhost 0.0.0.0; do
    [ ! -e "$alias" ] && ln -sf "${SITE_NAME}" "$alias"
done
cd ..

echo "[*] Site ${SITE_NAME} ready."
