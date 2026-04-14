#!/bin/bash
set -e

if [ ! -f /.benchpress_config ]; then
    echo "benchpress_config missing"
    exit 1
fi

TARGET_USER=$(python3 -c "import json; print(json.load(open('/.benchpress_config')).get('username',''))")
if [ -z "$TARGET_USER" ]; then
    echo "username not found"
    exit 1
fi

sudo -u "$TARGET_USER" screen -X -S codeserver quit || true
sudo -u "$TARGET_USER" screen -d -m -S codeserver \
    code-server "/home/$TARGET_USER/frappe-bench"
