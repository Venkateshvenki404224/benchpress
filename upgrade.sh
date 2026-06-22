#!/bin/bash
# BenchPress upgrade script
# Upgrades an existing BenchPress install end-to-end with a pre-upgrade backup
# gate and abort-on-failure, following docs/upgrading.md.
#
# Usage:
#   cd /path/to/frappe-bench
#   bash apps/benchpress/upgrade.sh <site-name> [target-ref] [--dry-run]
#
# Examples:
#   bash apps/benchpress/upgrade.sh sponge.localhost
#   bash apps/benchpress/upgrade.sh sponge.localhost version-16
#   bash apps/benchpress/upgrade.sh sponge.localhost --dry-run
#
# This is the scripted counterpart to the manual runbook in docs/upgrading.md.
# It does NOT roll back automatically (that is a later slice) — on failure it
# points you at the recorded revision and your backup so you can follow the
# runbook's Rollback section.

set -e

BENCH_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
APP_DIR="$BENCH_DIR/apps/benchpress"
ROLLBACK_FILE="/tmp/benchpress-rollback-sha"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${BLUE}[*]${NC} $1"; }
success() { echo -e "${GREEN}[✓]${NC} $1"; }
warn()    { echo -e "${YELLOW}[!]${NC} $1"; }
error()   { echo -e "${RED}[✗]${NC} $1"; exit 1; }

usage() {
    echo "Usage: bash apps/benchpress/upgrade.sh <site-name> [target-ref] [--dry-run]"
    echo ""
    echo "  <site-name>   Site to upgrade (required), e.g. sponge.localhost"
    echo "  [target-ref]  Git branch or tag to upgrade to (optional; defaults to"
    echo "                fast-forwarding the current branch)"
    echo "  --dry-run     Print every step without changing anything"
}

# --- Parse arguments ---

DRY_RUN=0
SITE_NAME=""
TARGET_REF=""

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        -h|--help) usage; exit 0 ;;
        -*) usage; error "Unknown option: $arg" ;;
        *)
            if [ -z "$SITE_NAME" ]; then
                SITE_NAME="$arg"
            elif [ -z "$TARGET_REF" ]; then
                TARGET_REF="$arg"
            else
                error "Unexpected argument: $arg"
            fi
            ;;
    esac
done

# run COMMAND... — execute it, or just print it in dry-run mode.
run() {
    if [ "$DRY_RUN" -eq 1 ]; then
        echo -e "${YELLOW}[dry-run]${NC} $*"
    else
        "$@"
    fi
}

echo ""
echo "=============================="
echo "  BenchPress Upgrade"
echo "=============================="
echo ""

if [ -z "$SITE_NAME" ]; then
    usage
    error "Site name required."
fi

# Upgrades touch the host bench (git, yarn, bench restart) — none of it belongs
# inside a container.
if [ -f "/.dockerenv" ]; then
    warn "Running inside a Docker container — run the upgrade on the host bench."
    warn "  bash apps/benchpress/upgrade.sh $SITE_NAME"
    exit 0
fi

# apps/frappe exists in every valid bench; this confirms we are at the bench root.
if [ ! -d "$BENCH_DIR/apps/frappe" ]; then
    error "Run this script from your frappe-bench (bash apps/benchpress/upgrade.sh). Found: $BENCH_DIR"
fi

if [ ! -d "$APP_DIR" ]; then
    error "BenchPress app not found at $APP_DIR"
fi

info "Bench directory : $BENCH_DIR"
info "Site            : $SITE_NAME"
if [ -n "$TARGET_REF" ]; then
    info "Target revision : $TARGET_REF"
else
    info "Target revision : (fast-forward current branch)"
fi
[ "$DRY_RUN" -eq 1 ] && warn "DRY RUN — no changes will be made"
echo ""

# --- Step 0: Pre-upgrade backup (the gate) ---

info "Step 0/5: Pre-upgrade backup (the gate)"

if [ "$DRY_RUN" -eq 1 ]; then
    echo -e "${YELLOW}[dry-run]${NC} bench --site $SITE_NAME backup --with-files"
    echo -e "${YELLOW}[dry-run]${NC} record current revision to $ROLLBACK_FILE"
else
    # The gate: if there is no backup, there is nothing to roll back to.
    if ! bench --site "$SITE_NAME" backup --with-files; then
        error "Backup failed — aborting. Nothing has changed and there is nothing to roll back to. Fix the backup (disk space, MariaDB, permissions) and re-run."
    fi
    success "Backup complete"

    ROLLBACK_SHA="$(git -C "$APP_DIR" rev-parse HEAD)"
    echo "$ROLLBACK_SHA" > "$ROLLBACK_FILE"
    success "Recorded rollback revision $ROLLBACK_SHA -> $ROLLBACK_FILE"
fi

echo ""

# From here on a failure leaves a partially-upgraded install, so guide the
# operator to the recorded revision and backup instead of failing silently.
on_failure() {
    echo ""
    echo -e "${RED}[✗] Upgrade failed after the backup.${NC}"
    echo "    Your install may be partially upgraded. To roll back:"
    echo "      1. Restore code: git -C apps/benchpress checkout \$(cat $ROLLBACK_FILE)"
    echo "      2. Restore data: bench --site $SITE_NAME restore <Step 0 backup>"
    echo "    See the Rollback section of docs/upgrading.md for the full procedure."
}
trap on_failure ERR

# --- Step 1: Update the app code ---

info "Step 1/5: Update app code"
run git -C "$APP_DIR" fetch origin --tags
if [ -n "$TARGET_REF" ]; then
    run git -C "$APP_DIR" checkout "$TARGET_REF"
else
    run git -C "$APP_DIR" pull --ff-only
fi
run bench pip install -e "$APP_DIR"
success "App code updated"
echo ""

# --- Step 2: Run database migrations ---

info "Step 2/5: Run database migrations"
run bench --site "$SITE_NAME" migrate
success "Migrations applied"
echo ""

# --- Step 3: Rebuild frontend assets ---

info "Step 3/5: Rebuild frontend assets"
run yarn --cwd "$APP_DIR/frontend" install
run yarn --cwd "$APP_DIR/frontend" build
run bench build --app benchpress
run bench --site "$SITE_NAME" clear-cache
success "Assets rebuilt"
echo ""

# --- Step 4: Restart services ---

info "Step 4/5: Restart services"
run bench restart
success "Services restarted (on a dev bench, restart 'bench start' yourself)"
echo ""

# --- Step 5: Verify health ---

info "Step 5/5: Verify health"
# A clean second migrate is a no-op — it confirms there are no pending patches.
run bench --site "$SITE_NAME" migrate
if [ "$DRY_RUN" -eq 1 ]; then
    echo -e "${YELLOW}[dry-run]${NC} bench --site $SITE_NAME execute benchpress.doctor.run"
else
    bench --site "$SITE_NAME" execute benchpress.doctor.run \
        || warn "doctor check unavailable or reported issues — review the output above"
fi
success "Verification complete"
echo ""

trap - ERR

echo "=============================="
echo "  Upgrade Complete"
echo "=============================="
echo ""
success "BenchPress is upgraded. Open the dashboard and confirm it loads:"
echo "    http://$SITE_NAME/frontend"
echo ""
echo "If anything looks wrong, roll back using the recorded revision and your"
echo "Step 0 backup — see docs/upgrading.md (Rollback)."
echo ""
