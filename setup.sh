#!/bin/bash
# BenchPress post-install setup script
# Run this once after: bench install-app benchpress
#
# Usage:
#   cd /path/to/frappe-bench
#   bash apps/benchpress/setup.sh <site-name> [--strict]
#
# Example:
#   bash apps/benchpress/setup.sh sponge.localhost
#
# --strict: exit non-zero if Docker userns-remap is absent or unverifiable
# (production hosts); default is warn-and-continue (dev hosts).
#
# VPN note: tunnels, peers and IP allocation are owned by the vpn_management
# app (wg-agent + VPN Peer / Network Pool DocTypes). This script only prepares
# Docker and host networking for BenchPress itself.

set -e

BENCH_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
BENCH_USER="$(whoami)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${BLUE}[*]${NC} $1"; }
success() { echo -e "${GREEN}[✓]${NC} $1"; }
warn()    { echo -e "${YELLOW}[!]${NC} $1"; }
error()   { echo -e "${RED}[✗]${NC} $1"; exit 1; }

# --- Parse arguments ---

SITE_NAME=""
STRICT=0

for arg in "$@"; do
    case "$arg" in
        --strict) STRICT=1 ;;
        -*) error "Unknown option: $arg. Usage: bash apps/benchpress/setup.sh <site-name> [--strict]" ;;
        *)
            if [ -z "$SITE_NAME" ]; then
                SITE_NAME="$arg"
            else
                error "Unexpected argument: $arg"
            fi
            ;;
    esac
done

echo ""
echo "=============================="
echo "  BenchPress Setup"
echo "=============================="
echo ""

if [ -z "$SITE_NAME" ]; then
    error "Site name required. Usage: bash apps/benchpress/setup.sh <site-name> [--strict]"
fi

# Every step needs host-level access (docker group, sysctl) — none of it
# works inside a container.
if [ -f "/.dockerenv" ]; then
    warn "Running inside a Docker container — host setup must be run on the host."
    warn "  bash apps/benchpress/setup.sh $SITE_NAME"
    exit 0
fi

# apps/frappe exists in every valid bench (dev or Docker); Procfile is
# dev-mode only and never written in containerised installs.
if [ ! -d "$BENCH_DIR/apps/frappe" ]; then
    error "Run this script from inside your frappe-bench directory. Found: $BENCH_DIR"
fi

info "Bench directory : $BENCH_DIR"
info "Site            : $SITE_NAME"
info "Bench user      : $BENCH_USER"
echo ""

# --- Step 1: Docker group ---

info "Step 1/4: Docker group"

if groups "$BENCH_USER" | grep -q '\bdocker\b'; then
    success "User '$BENCH_USER' is already in the docker group"
else
    info "Adding '$BENCH_USER' to the docker group..."
    sudo usermod -aG docker "$BENCH_USER"
    success "Added '$BENCH_USER' to docker group"
    warn "You must log out and back in (or run 'newgrp docker') for the group change to take effect"
    warn "Restart the bench after re-login: bench start"
fi

# Verify docker is accessible (may still fail if session hasn't refreshed)
if docker ps &>/dev/null; then
    success "Docker socket is accessible"
else
    warn "Docker socket not yet accessible in this session — log out and back in, then restart bench"
fi

echo ""

# --- Step 2: Docker user-namespace remap (container-root != host-root) ---

info "Step 2/4: Docker userns-remap"
if ! docker info &>/dev/null; then
    MSG="Cannot verify userns-remap — docker socket not accessible (re-login, then re-run)"
    [ "$STRICT" -eq 1 ] && error "$MSG" || warn "$MSG"
elif docker info --format '{{join .SecurityOptions ","}}' | grep -qE 'name=(userns|rootless)'; then
    success "Docker userns-remap (or rootless) is enabled — container root is unprivileged on the host"
else
    warn "Docker userns-remap is NOT enabled — in-container root maps to HOST root"
    warn "Lab users get container root; without remap that is one kernel bug from host root."
    warn "Enable it: add {\"userns-remap\": \"default\"} to /etc/docker/daemon.json, restart docker."
    warn "Details and migration caveats: apps/benchpress/docs/wireguard-setup.md#docker-userns-remap"
    [ "$STRICT" -eq 1 ] && error "--strict: refusing to continue without userns-remap"
fi

echo ""

# --- Step 3: Shared infrastructure (MariaDB + Redis) ---

info "Step 3/4: Shared infrastructure (MariaDB + Redis)"

COMPOSE_DIR="$BENCH_DIR/apps/benchpress/benchpress/config"
COMPOSE_FILE="$COMPOSE_DIR/docker-compose.yml"
ENV_FILE="$COMPOSE_DIR/.env"

if [ ! -f "$COMPOSE_FILE" ]; then
    error "docker-compose.yml not found at $COMPOSE_FILE"
fi

# Generate .env if it doesn't exist
if [ ! -f "$ENV_FILE" ]; then
    info "Generating .env file for shared infrastructure..."
    # Straight into the file, never through a shell variable: a variable holding it
    # can be exported into a child process or echoed by a later edit.
    cat > "$ENV_FILE" <<EOF
MARIADB_ROOT_PASSWORD=$(openssl rand -hex 16)
MARIADB_VERSION=10.6
MARIADB_MEM_LIMIT=1g
EOF
    success "Generated .env with random root password"
else
    success ".env file already exists"
fi

# Ensure benchpress Docker network exists
if docker network inspect benchpress &>/dev/null; then
    success "Docker network 'benchpress' already exists"
else
    info "Creating Docker network 'benchpress'..."
    docker network create --driver bridge --subnet 172.30.0.0/24 benchpress
    success "Docker network 'benchpress' created"
fi

# Ensure MariaDB data volume exists (marked external in compose)
if docker volume inspect benchpress-mariadb-data &>/dev/null; then
    success "Volume 'benchpress-mariadb-data' already exists"
else
    info "Creating volume 'benchpress-mariadb-data'..."
    docker volume create benchpress-mariadb-data
    success "Volume created"
fi

# Bring up MariaDB + Redis
info "Starting shared MariaDB and Redis containers..."
docker compose -f "$COMPOSE_FILE" up -d
success "Shared infrastructure is running"

# Wait for MariaDB to be ready
info "Waiting for MariaDB to accept connections..."
for i in $(seq 1 30); do
    # The image's own probe, which reads its credentials from a root-owned file inside the
    # container. Passing the root password with -p published it on every attempt, because
    # Docker puts an exec's command line into its event stream.
    if docker exec benchpress-mariadb healthcheck.sh --connect --innodb_initialized &>/dev/null; then
        success "MariaDB is ready"
        break
    fi
    if [ "$i" -eq 30 ]; then
        error "MariaDB did not become ready in 60 seconds"
    fi
    sleep 2
done

# Verify Redis
if docker exec benchpress-redis redis-cli ping 2>/dev/null | grep -q PONG; then
    success "Redis is ready"
else
    warn "Redis not responding — check 'docker logs benchpress-redis'"
fi

echo ""

# --- Step 4: IP forwarding ---

info "Step 4/4: IP forwarding"

SYSCTL_CONF="/etc/sysctl.d/99-benchpress.conf"

if sysctl net.ipv4.ip_forward | grep -q "= 1"; then
    success "IP forwarding is already enabled"
else
    info "Enabling IP forwarding..."
    sudo sysctl -w net.ipv4.ip_forward=1
    success "IP forwarding enabled (runtime)"
fi

if [ ! -f "$SYSCTL_CONF" ]; then
    info "Making IP forwarding persistent across reboots..."
    echo "net.ipv4.ip_forward = 1" | sudo tee "$SYSCTL_CONF" > /dev/null
    sudo sysctl -p "$SYSCTL_CONF" &>/dev/null || true
    success "Persisted to $SYSCTL_CONF"
else
    success "IP forwarding persistence already configured ($SYSCTL_CONF)"
fi

echo ""
echo "=============================="
echo "  Setup Complete"
echo "=============================="
echo ""

echo "Next steps:"
echo ""
echo "  1. If group change was needed: log out, log back in, then restart bench"
echo "     $ bench start"
echo ""
echo "  2. Open BenchPress Settings in Frappe Desk and set the Base Domain."
echo ""
echo "  3. VPN is managed by the vpn_management app — see the VPN workspace"
echo "     in Desk (WireGuard Server, Network Pool, VPN Peer) and make sure"
echo "     its wg-agent is running with the server's UDP port open."
echo ""
echo "  Done! Create a Lab and deploy your first bench."
echo ""
