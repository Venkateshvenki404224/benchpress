#!/bin/bash
# BenchPress post-install setup script
# Run this once after: bench install-app benchpress
#
# Usage:
#   cd /path/to/frappe-bench
#   bash apps/benchpress/setup.sh <site-name>
#
# Example:
#   bash apps/benchpress/setup.sh sponge.localhost

set -e

BENCH_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
SITE_NAME="${1:-}"
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

echo ""
echo "=============================="
echo "  BenchPress Setup"
echo "=============================="
echo ""

if [ -z "$SITE_NAME" ]; then
    error "Site name required. Usage: bash apps/benchpress/setup.sh <site-name>"
fi

if [ ! -f "$BENCH_DIR/Procfile" ]; then
    error "Run this script from inside your frappe-bench directory. Found: $BENCH_DIR"
fi

info "Bench directory : $BENCH_DIR"
info "Site            : $SITE_NAME"
info "Bench user      : $BENCH_USER"
echo ""

# --- Step 1: Docker group ---

info "Step 1/5: Docker group"

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

# --- Step 2: IP forwarding ---

info "Step 2/5: IP forwarding"

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

# --- Step 3: Sudoers for WireGuard ---

info "Step 3/5: Sudoers (WireGuard + Docker socket)"

SUDOERS_FILE="/etc/sudoers.d/benchpress"

WG_BIN="$(which wg 2>/dev/null || echo /usr/bin/wg)"
WG_QUICK_BIN="$(which wg-quick 2>/dev/null || echo /usr/bin/wg-quick)"

SUDOERS_LINE="$BENCH_USER ALL=(ALL) NOPASSWD: $WG_BIN, $WG_QUICK_BIN"

if [ -f "$SUDOERS_FILE" ] && grep -q "$BENCH_USER" "$SUDOERS_FILE"; then
    success "Sudoers entry already exists for '$BENCH_USER'"
else
    info "Writing sudoers entry to $SUDOERS_FILE..."
    echo "$SUDOERS_LINE" | sudo tee "$SUDOERS_FILE" > /dev/null
    sudo chmod 0440 "$SUDOERS_FILE"
    success "Sudoers configured"
fi

# Quick sanity check
if sudo -n wg show &>/dev/null 2>&1 || sudo -n wg show 2>&1 | grep -qv "password"; then
    success "Passwordless sudo for wg is working"
else
    warn "Could not verify passwordless sudo — check $SUDOERS_FILE manually"
fi

echo ""

# --- Step 4: WireGuard install check ---

info "Step 4/5: WireGuard tools"

if command -v wg &>/dev/null && command -v wg-quick &>/dev/null; then
    success "WireGuard tools already installed ($(wg --version 2>/dev/null || echo 'wg found'))"
else
    info "Installing WireGuard tools..."
    sudo apt-get update -qq
    sudo apt-get install -y --no-install-recommends wireguard wireguard-tools
    success "WireGuard installed"
fi

echo ""

# --- Step 5: WireGuard server init ---

info "Step 5/5: WireGuard server initialization"

if sudo wg show wg0 &>/dev/null 2>&1; then
    success "wg0 interface is already running"
    WG_PUBKEY=$(sudo wg show wg0 public-key 2>/dev/null || echo "")
else
    info "Initializing WireGuard server (wg0)..."
    cd "$BENCH_DIR"
    bench --site "$SITE_NAME" execute benchpress.wg_manager.setup_wg_server
    success "WireGuard server initialized"

    if sudo wg show wg0 &>/dev/null 2>&1; then
        WG_PUBKEY=$(sudo wg show wg0 public-key 2>/dev/null || echo "")
        success "wg0 is up"
    else
        warn "wg0 did not come up — run 'sudo wg-quick up wg0' manually"
        WG_PUBKEY=""
    fi
fi

echo ""
echo "=============================="
echo "  Setup Complete"
echo "=============================="
echo ""

if [ -n "$WG_PUBKEY" ]; then
    echo -e "${GREEN}WireGuard Server Public Key:${NC}"
    echo "  $WG_PUBKEY"
    echo ""
fi

echo "Next steps:"
echo ""
echo "  1. If group change was needed: log out, log back in, then restart bench"
echo "     $ bench start"
echo ""
echo "  2. Open BenchPress Settings in Frappe Desk:"
echo "     /app/benchpress-settings"
echo ""
echo "  3. Fill in:"
echo "     - WG Server Public Key  : (shown above)"
echo "     - WG Server Endpoint    : <your server's public IP>"
echo "     - WG Server Port        : 51820"
echo ""
echo "  4. Make sure UDP 51820 is open in your firewall / cloud security group"
echo "     $ sudo ufw allow 51820/udp"
echo ""
echo "  Done! Create a Lab and deploy your first bench."
echo ""
