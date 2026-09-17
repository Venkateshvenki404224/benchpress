#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Time how long one lab's golden dump takes to restore under four MariaDB configurations.

Each configuration runs in its own throwaway mariadb container named bp-restore-probe,
with no ports and a 2g memory limit. The shared benchpress-mariadb is never touched. Run it
off-peak: a restore loads the host's disk and CPU.

    scripts/restore_probe.sh                      the four configurations, against the crm lab
    scripts/restore_probe.sh --lab-tag <tag>      against another lab image
    scripts/restore_probe.sh --list               the four configurations and their flags

BENCHPRESS_SITE and BENCHPRESS_COMPOSE_DIR are read the way scripts/golden_drill.py reads them.
EOF
}

PROBE=bp-restore-probe
MARIADB_IMAGE=mariadb:${MARIADB_VERSION:-10.6}
DUMP_IN_IMAGE=/opt/benchpress/golden/site.sql.gz
DATABASE=restore_probe
SITE=${BENCHPRESS_SITE:-frontend}
COMPOSE_DIR=${BENCHPRESS_COMPOSE_DIR:-/home/ubuntu/benchpress_devops}
BASE_FILE="$(cd "$(dirname "$0")/.." && pwd)/benchpress/config/docker-compose.yml"
CONFIGURATIONS=(today durable-off per-table-off tmpfs)
DURABLE_OFF="--innodb-flush-log-at-trx-commit=2 --skip-log-bin --table-open-cache=4000 --table-definition-cache=4000"
TMPFS_MOUNT=/var/lib/mysql:rw,size=1g,uid=999,gid=999

fail() {
    echo "restore_probe: $*" >&2
    exit 1
}

base_flags() {
    awk '
        /^  [a-z-]+:$/ { in_mariadb = ($1 == "mariadb:") }
        in_mariadb && /command: >/ { in_command = 1; next }
        in_command && /^ +--/ { printf "%s%s", separator, $1; separator = " "; next }
        in_command && !/^ +mariadbd$/ { exit }
    ' "$BASE_FILE"
}

flags_for() {
    case "$1" in
        today) echo "$TODAY" ;;
        durable-off) echo "$TODAY $DURABLE_OFF" ;;
        per-table-off) echo "$TODAY $DURABLE_OFF --innodb-file-per-table=OFF" ;;
        tmpfs) echo "$TODAY $DURABLE_OFF --skip-innodb-doublewrite --innodb-flush-method=fsync" ;;
    esac
}

storage_for() {
    if [ "$1" = tmpfs ]; then
        echo "--tmpfs $TMPFS_MOUNT"
    fi
}

list() {
    local name storage
    for name in "${CONFIGURATIONS[@]}"; do
        storage=$(storage_for "$name")
        printf '%-14s %s\n' "$name" "$(flags_for "$name")${storage:+ $storage}"
    done
}

crm_lab_tag() {
    { (cd "$COMPOSE_DIR" && docker compose exec -T backend bench --site "$SITE" execute frappe.db.get_value \
        --args '["Lab", "crm", "image_tag"]' </dev/null) || true; } | tail -n 1 | tr -d '"'
}

host_line() {
    free -b | awk -v cpus="$(nproc)" '
        $1 == "Mem:" { total = $2; available = $7 }
        $1 == "Swap:" { swap_total = $2; swap_used = $3 }
        END {
            gib = 1024 ^ 3
            printf "host: %.2f GiB RAM, %.2f GiB available, swap %.2f of %.2f GiB in use, %s CPUs\n",
                total / gib, available / gib, swap_used / gib, swap_total / gib, cpus
        }'
}

remove_leftovers() {
    docker rm -f "$PROBE" >/dev/null 2>&1 || true
    if [ -n "${HOLDER:-}" ]; then
        docker rm -f "$HOLDER" >/dev/null 2>&1 || true
    fi
    rm -rf "$WORK"
}

copy_dump() {
    HOLDER=$(docker create "$LAB_TAG")
    docker cp "$HOLDER:$DUMP_IN_IMAGE" "$DUMP" >/dev/null || fail "$LAB_TAG carries no $DUMP_IN_IMAGE"
    docker rm "$HOLDER" >/dev/null
    HOLDER=
    [ -s "$DUMP" ] || fail "the dump in $LAB_TAG is empty"
}

wait_until_serving() {
    local attempt
    for attempt in $(seq 120); do
        if docker exec -e MYSQL_PWD="$PASSWORD" "$PROBE" \
            mariadb-admin --protocol=tcp -h127.0.0.1 -uroot ping >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    fail "$PROBE did not answer after $attempt seconds"
}

probe() {
    local name=$1 storage flags started ended elapsed
    read -ra storage <<< "$(storage_for "$name")"
    read -ra flags <<< "$(flags_for "$name")"
    docker run -d --rm --name "$PROBE" --memory 2g --memory-swap 2g "${storage[@]}" \
        -e MARIADB_ROOT_PASSWORD="$PASSWORD" "$MARIADB_IMAGE" mariadbd "${flags[@]}" >/dev/null
    wait_until_serving
    docker exec -e MYSQL_PWD="$PASSWORD" "$PROBE" \
        mariadb --protocol=tcp -h127.0.0.1 -uroot -e "CREATE DATABASE $DATABASE"

    started=$(date +%s%3N)
    gzip -cd "$DUMP" \
        | sed '/\/\*M\{0,1\}!999999\\- enable the sandbox mode \*\//d' \
        | sed '/\/\*![0-9]* DEFINER=[^ ]* SQL SECURITY DEFINER \*\//d' \
        | docker exec -i -e MYSQL_PWD="$PASSWORD" "$PROBE" \
            mariadb --protocol=tcp -h127.0.0.1 -uroot "$DATABASE"
    ended=$(date +%s%3N)
    elapsed=$((ended - started))

    printf '%-14s %d.%d s\n' "$name" $((elapsed / 1000)) $((elapsed % 1000 / 100))
    docker stop "$PROBE" >/dev/null
    while docker inspect "$PROBE" >/dev/null 2>&1; do sleep 1; done
}

TODAY=$(base_flags)
[ -n "$TODAY" ] || fail "no mariadbd flags found in $BASE_FILE"

LAB_TAG=
while [ $# -gt 0 ]; do
    case "$1" in
        --list) list; exit 0 ;;
        --lab-tag) LAB_TAG=${2:?--lab-tag needs a tag}; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
done

if docker inspect "$PROBE" >/dev/null 2>&1; then
    fail "a container named $PROBE already exists; another probe may be running"
fi
LAB_TAG=${LAB_TAG:-$(crm_lab_tag)}
[ -n "$LAB_TAG" ] || fail "could not read the crm lab's image tag from $SITE; pass --lab-tag"

WORK=$(mktemp -d)
DUMP="$WORK/site.sql.gz"
HOLDER=
PASSWORD=$(head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9')
trap remove_leftovers EXIT

copy_dump
echo "probe: $LAB_TAG, dump $(stat -c %s "$DUMP") bytes, $(date -u +%Y-%m-%dT%H:%MZ)"
host_line
for name in "${CONFIGURATIONS[@]}"; do
    probe "$name"
done
