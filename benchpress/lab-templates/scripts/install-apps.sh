#!/bin/bash
set -e

APPS_JSON="$1"

if [ -z "$APPS_JSON" ] || [ "$APPS_JSON" = "[]" ]; then
    echo "[install-apps] No apps to install."
    exit 0
fi

echo "$APPS_JSON" | python3 -c "
import sys, json
apps = json.load(sys.stdin)
for app in apps:
    if app.get('app_name') == 'frappe':
        continue
    print(f\"{app['app_name']}|{app['git_url']}|{app['branch']}\")
" | while IFS='|' read -r app_name git_url branch; do
    echo "[install-apps] Installing ${app_name} (branch: ${branch})..."
    bench get-app --branch "${branch}" --skip-assets "${git_url}"
    echo "[install-apps] ${app_name} installed."
done
