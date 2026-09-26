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
# Cap the Node.js V8 heap so code-server GCs aggressively instead of
# growing until the container hits its memory limit and gets OOM-killed.
# 512 MB is sufficient for editing; the process runs fine and just GCs more.
sudo -u "$TARGET_USER" screen -d -m -S codeserver \
    env NODE_OPTIONS="--max-old-space-size=512" \
    code-server "/home/$TARGET_USER/frappe-bench"
