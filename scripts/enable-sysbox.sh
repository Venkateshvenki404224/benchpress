#!/usr/bin/env bash
#
# scripts/enable-sysbox.sh — register the Sysbox runtime with this host's Docker
# daemon, so a bench container can have root that is not host root.
#
# A bench gives its user in-container root; sudo for bench work is the point of
# the product. Under `runc` that root is host root wearing a namespace, so the
# only thing between a bench and every other tenant's database is `runc` itself.
# Sysbox runs a container in a user namespace: container root maps to an
# unprivileged host UID. In-container root stays, the escape path closes.
#
# Nothing installs this for you. It restarts the Docker daemon, so it is a
# decision an operator makes, not a step an installer takes.
#
#   sudo scripts/enable-sysbox.sh                    # confirm, then do it
#   sudo scripts/enable-sysbox.sh --yes              # unattended
#   sudo scripts/enable-sysbox.sh --skip-reclaim     # disk already has room
#   sudo scripts/enable-sysbox.sh --version 0.6.7    # a different release
#
# `runc` stays the daemon's default-runtime, so nothing already running changes
# behaviour. BenchPress names `sysbox-runc` explicitly on the containers it wants
# isolated: set a Bench Instance's Runtime field to `sysbox`
# (benchpress/docker_manager.py, CONTAINER_RUNTIMES).
#
# Re-runnable. On a host where Sysbox is already registered it re-runs the only
# check that proves anything — creating a container — and reports that instead.
#
# Two things this script will not do, because both are worse than stopping:
#
#   * It never runs `docker system prune -a`. `-a` deletes every image not
#     attached to a *running* container, which on a BenchPress host includes the
#     lab images that Draft and Stopped benches point at. That damage passes every
#     "the site loads" check and surfaces at the next redeploy, hours later.
#   * It never removes a container. It records what was running, and starts those
#     again after the daemon restart.

set -euo pipefail

# --- What an operator sets ----------------------------------------------------
#
# Every one of these has a default that is right for a stock BenchPress
# deployment. Export a different value, or edit it here, if yours differs.

# The container running the BenchPress site, used only to sweep unreferenced lab
# images before the install. `<compose project>_backend` for a compose deployment;
# the project defaults to `benchpress`.
BENCH_BACKEND_CONTAINER="${BENCH_BACKEND_CONTAINER:-benchpress_backend}"

# The BenchPress site name. `frontend` is the invariant this repo is built on.
SITE_NAME="${SITE_NAME:-frontend}"

SYSBOX_VERSION="0.7.1"
SYSBOX_DEB_URL=""
MIN_FREE_MB=2048
ASSUME_YES=0
SKIP_RECLAIM=0

usage() {
  cat <<'USAGE'
Usage: sudo scripts/enable-sysbox.sh [options]

  --version <x.y.z>  Sysbox CE release to install (default: 0.7.1)
  --url <url>        Full .deb URL, overriding --version
  --min-free <mb>    Refuse to install below this free space (default: 2048)
  --yes              Do not ask before restarting the Docker daemon
  --skip-reclaim     Skip the disk reclamation pass
  -h, --help         This message

Environment:
  BENCH_BACKEND_CONTAINER  Container running the BenchPress site (default: benchpress_backend)
  SITE_NAME                BenchPress site (default: frontend)
  DOCKER_BIP               Address for docker0 (default: 172.17.0.1/16)
  DOCKER_POOL_BASE         Pool new Docker networks are cut from (default: 172.20.0.0/14)
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)      SYSBOX_VERSION="${2:?--version needs a value}"; shift 2 ;;
    --url)          SYSBOX_DEB_URL="${2:?--url needs a value}"; shift 2 ;;
    --min-free)     MIN_FREE_MB="${2:?--min-free needs a value}"; shift 2 ;;
    --yes)          ASSUME_YES=1; shift ;;
    --skip-reclaim) SKIP_RECLAIM=1; shift ;;
    -h|--help)      usage; exit 0 ;;
    *)              usage; echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

log()  { printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"; }
die()  { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

DAEMON_JSON=/etc/docker/daemon.json
BACKUP=""

# --- The runtime gate ---------------------------------------------------------
#
# `systemctl is-active sysbox` and `docker info` listing sysbox-runc are both
# true in the failure mode this whole exercise exists to catch: a registered
# runtime that cannot create a single container. Creating one is the only check
# that means anything, and the uid_map is the only proof of what it created --
# HostConfig.Runtime records what was asked for.

gate() {
  local uid_map out
  # Keep the output. Discarding it reports a failed `alpine` pull -- a rate limit, an
  # air-gapped host -- as a Sysbox fault, and sends the operator to an AppArmor log that
  # will show nothing.
  out="$(docker run --rm --runtime=sysbox-runc alpine echo ok 2>&1)" \
    || { printf '%s\n' "${out}" >&2; return 1; }
  uid_map="$(docker run --rm --runtime=sysbox-runc alpine cat /proc/self/uid_map 2>/dev/null)" \
    || return 1
  log "uid_map inside a Sysbox container: ${uid_map}"
  [[ "$(echo "${uid_map}" | awk 'NR==1 {print $1, $2}')" != "0 0" ]] \
    || die "Sysbox ran the container but container root is still host root (identity map). Do not treat this host as isolated."
  log "Sysbox works: container root maps to an unprivileged host UID."
}

# --- AppArmor -----------------------------------------------------------------
#
# Ubuntu's fusermount3 profile allow-lists mount DESTINATIONS -- $HOME, /mnt,
# /media, /tmp, /run/user, a few flatpak caches. Sysbox mounts its per-container
# FUSE filesystem under /var/lib/sysboxfs/<id>/, which is not among them, so the
# kernel refuses every Sysbox container:
#
#   apparmor="DENIED" operation="mount" info="failed mntpnt match" error=-13
#     profile="fusermount3" name="/var/lib/sysboxfs/<id>/" fstype="fuse"
#
# Docker reports that as "failed to pre-register with sysbox-fs: rpc error", which
# names neither FUSE nor AppArmor. It is the registered-but-broken failure exactly:
# sysbox-runc is in `docker info` and all three units are active.
#
# The profile ends with `include if exists <local/fusermount3>`, so a local file is
# the supported extension point -- no complain mode, no disabled profile. Undo by
# deleting it and re-running apparmor_parser -r.

ensure_fusermount_apparmor() {
  local profile=/etc/apparmor.d/fusermount3
  local override=/etc/apparmor.d/local/fusermount3

  [[ -f "${profile}" ]] || return 0
  grep -q "include if exists <local/fusermount3>" "${profile}" || {
    log "WARNING: ${profile} has no local include; if the gate fails, that is why"
    return 0
  }
  if [[ -f "${override}" ]] && grep -q "/var/lib/sysboxfs" "${override}"; then
    log "AppArmor override for /var/lib/sysboxfs already present"
    return 0
  fi

  log "Allowing fusermount3 to mount under /var/lib/sysboxfs (AppArmor local override)"
  mkdir -p "$(dirname "${override}")"
  cat >>"${override}" <<'AAEOF'
# Sysbox mounts a FUSE filesystem per container under /var/lib/sysboxfs/<id>/.
# Flags match the kernel's denial exactly: rw, nosuid, nodev.
mount fstype=fuse options=(nosuid,nodev,rw) {sysboxfs,/dev/fuse} -> /var/lib/sysboxfs/**/,
umount /var/lib/sysboxfs/**/,
AAEOF
  apparmor_parser -r "${profile}" \
    || die "could not reload ${profile}. Remove ${override} and reload it by hand."
}

# --- Restart, and put back what the restart stopped ---------------------------
#
# Bench containers carry no restart policy, so a daemon restart stops them and
# nothing brings them back. This records what was running, restarts, waits for the
# daemon, and starts those again. It never removes a container: a removed bench is
# not recoverable by starting anything.

restart_docker_and_restore() {
  local running cid name
  running="$(docker ps --format '{{.ID}}')"

  log "Restarting the Docker daemon"
  systemctl restart docker

  for _ in $(seq 30); do
    docker info >/dev/null 2>&1 && break
    sleep 2
  done
  docker info >/dev/null 2>&1 \
    || die "the daemon did not come back. Restore the config: cp ${BACKUP:-<no backup: ${DAEMON_JSON} did not exist>} ${DAEMON_JSON} && systemctl restart docker"

  for cid in ${running}; do
    if [[ "$(docker inspect -f '{{.State.Running}}' "${cid}" 2>/dev/null)" == "false" ]]; then
      name="$(docker inspect -f '{{.Name}}' "${cid}" 2>/dev/null | sed 's|^/||')"
      log "Starting ${cid} again (${name})"
      docker start "${cid}" >/dev/null || log "WARNING: ${cid} (${name}) did not start; check it by hand"
    fi
  done
}

# --- Preflight ----------------------------------------------------------------

[[ $EUID -eq 0 ]] || die "run this with sudo; it installs a package and restarts the Docker daemon"
[[ -d /run/systemd/system ]] || die "no systemd on this host; Sysbox ships systemd units and has no other supervisor"
command -v docker >/dev/null || die "docker is not installed"
docker info >/dev/null 2>&1 || die "the Docker daemon is not responding"

# shellcheck disable=SC1091
. /etc/os-release
case "${ID:-}" in
  ubuntu|debian) ;;
  *) die "unsupported distro '${ID:-unknown}'; Sysbox CE ships .deb packages only" ;;
esac

ARCH="$(dpkg --print-architecture)"
case "${ARCH}" in
  amd64|arm64) ;;
  *) die "unsupported architecture '${ARCH}'; Sysbox CE builds amd64 and arm64 only" ;;
esac

log "Host: ${PRETTY_NAME:-${ID}} ${ARCH}, kernel $(uname -r), systemd $(systemctl --version | head -1 | awk '{print $2}')"
log "Docker default-runtime: $(docker info --format '{{.DefaultRuntime}}'), storage driver: $(docker info --format '{{.Driver}}')"

if docker info --format '{{json .Runtimes}}' | grep -q 'sysbox-runc'; then
  log "sysbox-runc is already registered; re-running the container gate instead of installing."
  # A host can be registered and still blocked by the AppArmor profile, which is
  # the whole reason this branch does not just call gate().
  ensure_fusermount_apparmor
  gate || die "sysbox-runc is registered but cannot create a container.
Read both, in this order -- the first names the cause, the second only the symptom:
  dmesg -T | grep -i 'apparmor.*DENIED'
  journalctl -u sysbox-mgr -u sysbox-fs -n 200"
  exit 0
fi

# --- Disk ---------------------------------------------------------------------
#
# Sysbox needs room, and a daemon restart is a bad moment to discover the
# partition is full. Enumerate before deleting, and stop rather than reach for
# the destructive flag.

if [[ ${SKIP_RECLAIM} -eq 0 ]]; then
  log "Before reclamation:"
  df -h /
  docker system df
  log "Dangling images:"
  docker images -f dangling=true --format '  {{.ID}}  {{.Size}}  {{.Repository}}:{{.Tag}}' || true

  # `prune -f` is documented as dangling-only. On the containerd image store that
  # is not always what happens: it has removed TAGGED base images that Labs still
  # build against. Recoverable -- they re-pull -- but not free, and invisible
  # unless someone diffs the tags. So diff them.
  tags_before="$(mktemp)"; tags_after="$(mktemp)"
  docker images --format '{{.Repository}}:{{.Tag}}' | grep -v '^<none>:' | sort -u >"${tags_before}"

  log "Pruning stopped containers, dangling images and unused networks"
  docker system prune -f

  docker images --format '{{.Repository}}:{{.Tag}}' | grep -v '^<none>:' | sort -u >"${tags_after}"
  if ! comm -23 "${tags_before}" "${tags_after}" | grep -q .; then
    log "No tagged image was removed by the prune"
  else
    log "WARNING: the prune removed these TAGGED images; re-pull any you still need:"
    comm -23 "${tags_before}" "${tags_after}" | sed 's/^/  docker pull /'
  fi
  rm -f "${tags_before}" "${tags_after}"

  # Lab images no Lab row still points at. The app knows which those are; docker
  # does not, which is exactly why `prune -a` is the wrong tool here.
  if docker inspect -f '{{.State.Running}}' "${BENCH_BACKEND_CONTAINER}" 2>/dev/null | grep -qx true; then
    log "Sweeping unreferenced lab images through ${BENCH_BACKEND_CONTAINER}"
    docker exec "${BENCH_BACKEND_CONTAINER}" \
      bench --site "${SITE_NAME}" execute benchpress.image_cache.sweep_cached_images || true
  else
    log "${BENCH_BACKEND_CONTAINER} is not running; skipping the lab image sweep"
  fi

  log "After reclamation:"
  df -h /
fi

FREE_MB="$(df -Pm / | awk 'NR==2 {print $4}')"
if (( FREE_MB < MIN_FREE_MB )); then
  cat >&2 <<EOF

Only ${FREE_MB} MB free on /, below the ${MIN_FREE_MB} MB this script insists on.

Images \`docker system prune -a\` would delete, which this script will not run:

$(docker images --format '  {{.Repository}}:{{.Tag}}  {{.Size}}' | sort)

Some of those are lab images that Draft and Stopped benches still point at.
Decide against the Lab and Bench Instance tables first, delete by tag, then
re-run. Unused volumes are left alone too: they may still hold bench data.
EOF
  exit 1
fi

# --- Download -----------------------------------------------------------------

DEB_URL="${SYSBOX_DEB_URL:-https://downloads.nestybox.com/sysbox/releases/v${SYSBOX_VERSION}/sysbox-ce_${SYSBOX_VERSION}-0.linux_${ARCH}.deb}"

if [[ ${ASSUME_YES} -eq 0 ]]; then
  cat <<EOF

About to install Sysbox CE from:
  ${DEB_URL}

and restart the Docker daemon. Containers without a restart policy stop when the
daemon does; this script starts the ones that were running again afterwards, and
removes nothing. The bench containers running right now:

$(docker ps --filter label=benchpress.managed=true --format '  {{.Names}}  {{.Image}}  {{.Status}}')

EOF
  read -r -p "Proceed? [y/N] " reply
  [[ "${reply}" =~ ^[Yy]$ ]] || die "aborted"
fi

TMPDIR_DEB="$(mktemp -d)"
trap 'rm -rf "${TMPDIR_DEB}"' EXIT
DEB_PATH="${TMPDIR_DEB}/sysbox-ce.deb"

log "Downloading ${DEB_URL}"
curl -fsSL -o "${DEB_PATH}" "${DEB_URL}" \
  || die "download failed. Check the release exists: https://github.com/nestybox/sysbox/releases"

# --- Docker network pre-configuration -----------------------------------------
#
# The .deb's debconf `config` script REFUSES to install — exit 1, nothing done —
# when Docker is running, has containers, and daemon.json lacks BOTH `bip` and
# `default-address-pools`. It wants to restart the daemon to set them and will not
# do that under live containers. Setting them here first means its
# docker_restart_required() returns false, so `postinst` adds only the runtime and
# reloads with SIGHUP instead of restarting: the bench containers are never
# touched by the installer, and the one restart that happens is this script's.
#
# It greps rather than parses: `^[ ]+"bip": "[0-9.]+.*"`. The file must be written
# indented — json.dumps(indent=2) satisfies it, compact JSON does not.
#
# CHECK THE POOL AGAINST YOUR OWN NETWORK BEFORE RUNNING THIS. Docker cuts every
# network it creates from here on out of DOCKER_POOL_BASE, and a pool that
# overlaps something the host must reach blackholes it. The defaults avoid:
#   172.17.0.0/16   docker0 itself; `bip` only makes the existing value explicit
#   172.30.0.0/24   the lab network (benchpress/docker_manager.py, ensure_network)
# They do NOT know about your VPC, your LAN, your VPN, or the compose network of
# whatever orchestrates this host. Compare with `ip route` first, and override
# DOCKER_POOL_BASE if 172.20.0.0/14 (172.20.x - 172.23.x) collides.
#
# `features.time-namespaces: false` goes in the same write. Docker 29.5.0 made
# private time namespaces the container default (moby/moby#52326) and sysbox-runc
# does not implement that namespace, so without it every Sysbox container dies
# with `namespace {"time" ""} does not exist`. Upgrading Sysbox does not help.
#
# `default-runtime` is only ever set if absent, and only to runc. Flipping it
# would change every container on this host, not only BenchPress's.

DOCKER_BIP="${DOCKER_BIP:-172.17.0.1/16}"
DOCKER_POOL_BASE="${DOCKER_POOL_BASE:-172.20.0.0/14}"

mkdir -p /etc/docker
if [[ -f "${DAEMON_JSON}" ]]; then
  BACKUP="${DAEMON_JSON}.$(date -u +%Y%m%dT%H%M%SZ).bak"
  cp -a "${DAEMON_JSON}" "${BACKUP}"
  log "Backed up ${DAEMON_JSON} to ${BACKUP}"
fi

log "Pre-configuring ${DAEMON_JSON} so the installer does not need its own restart"
python3 - "${DAEMON_JSON}" "${DOCKER_BIP}" "${DOCKER_POOL_BASE}" <<'PY'
import json
import sys
from pathlib import Path

path, bip, pool_base = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
config = json.loads(path.read_text()) if path.exists() else {}
config.setdefault("bip", bip)
config.setdefault("default-address-pools", [{"base": pool_base, "size": 24}])
config.setdefault("default-runtime", "runc")
config.setdefault("features", {})["time-namespaces"] = False
path.write_text(json.dumps(config, indent=2) + "\n")
print(json.dumps(config, indent=2))
PY

restart_docker_and_restore

# --- Install ------------------------------------------------------------------

log "Installing"
DEBIAN_FRONTEND=noninteractive apt-get install -y "${DEB_PATH}"

command -v sysbox-runc >/dev/null || die "the package installed but sysbox-runc is not on PATH"
SYSBOX_BIN="$(command -v sysbox-runc)"
log "sysbox-runc at ${SYSBOX_BIN}: $(sysbox-runc --version | head -1)"

# postinst adds the runtime itself and SIGHUPs dockerd. Assert it rather than
# assume it: a runtime the daemon has not picked up fails the gate below with a
# message about the runtime, not about the reload.
if ! docker info --format '{{json .Runtimes}}' | grep -q 'sysbox-runc'; then
  log "the installer did not register sysbox-runc with the running daemon; adding it and restarting"
  python3 - "${DAEMON_JSON}" "${SYSBOX_BIN}" <<'PY'
import json
import sys
from pathlib import Path

path, sysbox_bin = Path(sys.argv[1]), sys.argv[2]
config = json.loads(path.read_text())
config.setdefault("runtimes", {})["sysbox-runc"] = {"path": sysbox_bin}
path.write_text(json.dumps(config, indent=2) + "\n")
PY
  restart_docker_and_restore
fi

ensure_fusermount_apparmor

# --- Verdict ------------------------------------------------------------------

log "default-runtime is now: $(docker info --format '{{.DefaultRuntime}}')"
gate || die "sysbox-runc is registered but cannot create a container -- the exact failure this gate exists for.
Nothing else on the host changed; runc is still the default, and every container is untouched.
Read both, in this order -- the first names the cause, the second only the symptom:
  dmesg -T | grep -i 'apparmor.*DENIED'
  journalctl -u sysbox-mgr -u sysbox-fs -n 200"

log "Done. Set a Bench Instance's Runtime field to 'sysbox' to use it."
