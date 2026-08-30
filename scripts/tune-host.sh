#!/usr/bin/env bash
#
# scripts/tune-host.sh — raise this host's kernel ceilings to what a dense bench
# fleet needs, and prove afterwards that the raise took.
#
# Every ceiling a bench fleet runs into is host-wide: one pty pool, one pid space,
# one neighbour table, one conntrack table. Left at whatever the machine image
# shipped, the platform's real limit is a number nobody chose. This writes the
# knobs measured below target into a single drop-in, states the arithmetic beside
# each value, and leaves the rest to whatever set them.
#
# BenchPress cannot do this from inside its own container: /proc/sys belongs to
# the host, and the three knobs the Diagnostics page reads are read-only there.
# The `kernel_ceilings` row reports the gap; this script is what closes it.
#
#   sudo scripts/tune-host.sh                        # confirm, then do it
#   sudo scripts/tune-host.sh --yes                  # unattended
#   sudo scripts/tune-host.sh --benches 2000 --yes   # size for a bigger fleet
#
# Re-runnable. A second run with the same arguments renders the same file, applies
# it again, and reports the same values.
#
# Undo: remove /etc/sysctl.d/99-benchpress-density.conf and run `sysctl --system`.
# Every value returns to whatever the machine image set. Nothing else on the host
# is touched — no daemon restarted, no unit installed, no container stopped.
#
# What this script will not do:
#
#   * It never writes kernel.threads-max. That is sized from RAM at boot, and
#     raising it past what memory supports converts a clean refusal into an OOM
#     kill. It is reported, with the bench count it implies, and left alone.
#   * It never trusts the file it just wrote. `sysctl --system` exits 0 when the
#     files parse, not when the values take: /etc/sysctl.d is read in lexical
#     order and the last writer of a key wins, so any drop-in sorting after ours
#     and naming one of these knobs silently overrides it. The gate below re-reads
#     /proc/sys and names the file that won.

set -euo pipefail

SYSCTL_CONF=/etc/sysctl.d/99-benchpress-density.conf

# Defaults, and where they come from. Both match `benchpress/placement.py`
# (DEFAULT_SLOTS_PER_BRIDGE, DEFAULT_BRIDGE_COUNT), which is also what
# `benchpress/diagnostics.py` sizes the `kernel_ceilings` row against. Change the
# BenchPress Settings fields and this host's sizing disagrees with the report
# until you pass the same number here.
BENCHES=1000
BRIDGES=16

# The per-bench costs every target below is built from. Each one is a constant in
# the app, not a guess:
#   TERMINALS_PER_BENCH, PTY_ROOT_RESERVE, CONNTRACK_PER_BENCH  benchpress/diagnostics.py
#   BENCH_PIDS_LIMIT (DEFAULT_PIDS_LIMIT)                       benchpress/docker_manager.py
#   BRIDGE_DEVICE_PREFIX                                        benchpress/placement.py
TERMINALS_PER_BENCH=8
PTY_ROOT_RESERVE=1024
BENCH_PIDS_LIMIT=500
FILES_PER_BENCH=1024
HOST_FILE_RESERVE=65536
CONNTRACK_PER_BENCH=256
SYN_BACKLOG_PER_BENCH=8
BRIDGE_DEVICE_PREFIX=bpbr

# A 64-bit kernel refuses anything larger, so the arithmetic stops here.
PID_MAX_KERNEL_CEILING=4194304

ASSUME_YES=0

usage() {
  cat <<USAGE
Usage: sudo scripts/tune-host.sh [options]

  --benches <n>  Bench count every value is sized against (default: ${BENCHES})
  --bridges <n>  Bench bridges to enable proxy ARP on (default: ${BRIDGES})
  --yes          Do not ask before writing ${SYSCTL_CONF}
  -h, --help     This message
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --benches) BENCHES="${2:?--benches needs a value}"; shift 2 ;;
    --bridges) BRIDGES="${2:?--bridges needs a value}"; shift 2 ;;
    --yes)     ASSUME_YES=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *)         usage; echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

log() { printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"; }
die() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

[[ "${BENCHES}" =~ ^[0-9]+$ && "${BENCHES}" -gt 0 ]] || die "--benches must be a positive integer"
[[ "${BRIDGES}" =~ ^[0-9]+$ && "${BRIDGES}" -gt 0 ]] || die "--bridges must be a positive integer"
[[ $EUID -eq 0 ]] || die "run this with sudo; it writes ${SYSCTL_CONF} and changes kernel limits for everything on this host"
command -v sysctl >/dev/null || die "sysctl is not on PATH"

# --- The knob table -----------------------------------------------------------
#
# One input — the bench count — decides every target, and the arithmetic behind
# each one is written into the drop-in as the comment above the knob.

KNOBS=(
  kernel.pty.max
  kernel.pid_max
  fs.file-max
  fs.nr_open
  net.netfilter.nf_conntrack_max
  net.ipv4.neigh.default.gc_thresh1
  net.ipv4.neigh.default.gc_thresh2
  net.ipv4.neigh.default.gc_thresh3
  net.core.netdev_max_backlog
  net.ipv4.tcp_max_syn_backlog
)

declare -A TARGET WHY

build_knob_table() {
  local pid_max gc2
  pid_max=$(( BENCHES * BENCH_PIDS_LIMIT ))
  (( pid_max > PID_MAX_KERNEL_CEILING )) && pid_max=${PID_MAX_KERNEL_CEILING}
  gc2=$(( BENCHES * 2 )); (( gc2 < 8192 )) && gc2=8192

  TARGET[kernel.pty.max]=$(( BENCHES * TERMINALS_PER_BENCH + PTY_ROOT_RESERVE ))
  WHY[kernel.pty.max]="${TERMINALS_PER_BENCH} terminals per bench (code-server and ssh) x ${BENCHES} benches
# + ${PTY_ROOT_RESERVE} held back for root by kernel.pty.reserve"

  TARGET[kernel.pid_max]=${pid_max}
  WHY[kernel.pid_max]="${BENCH_PIDS_LIMIT} pids per bench x ${BENCHES} benches, capped at the kernel's own
# ${PID_MAX_KERNEL_CEILING}"

  TARGET[fs.file-max]=$(( BENCHES * FILES_PER_BENCH + HOST_FILE_RESERVE ))
  WHY[fs.file-max]="${FILES_PER_BENCH} open files per bench x ${BENCHES} benches
# + ${HOST_FILE_RESERVE} for the host itself"

  TARGET[fs.nr_open]=1048576
  WHY[fs.nr_open]="Per process, so it does not scale with the bench count: it is the ceiling
# fs.file-max is shared out under"

  TARGET[net.netfilter.nf_conntrack_max]=$(( BENCHES * CONNTRACK_PER_BENCH ))
  WHY[net.netfilter.nf_conntrack_max]="${CONNTRACK_PER_BENCH} tracked flows per bench x ${BENCHES} benches"

  TARGET[net.ipv4.neigh.default.gc_thresh1]=4096
  WHY[net.ipv4.neigh.default.gc_thresh1]="A floor, not a ceiling: below it the kernel never garbage-collects. Under the
# working set it evicts entries it is about to need, which reads as intermittent
# packet loss between containers"

  TARGET[net.ipv4.neigh.default.gc_thresh2]=${gc2}
  WHY[net.ipv4.neigh.default.gc_thresh2]="2 neighbour entries per bench (its own address and the gateway it holds)
# x ${BENCHES} benches, floor 8192"

  TARGET[net.ipv4.neigh.default.gc_thresh3]=$(( gc2 * 2 ))
  WHY[net.ipv4.neigh.default.gc_thresh3]="Twice the soft threshold, so a burst has room before the kernel drops"

  TARGET[net.core.netdev_max_backlog]=16384
  WHY[net.core.netdev_max_backlog]="One broadcast on a full 1024-port bridge is 1024 packets, and the bridge count
# rather than the bench count is what fills this queue. At the stock 1000 a single
# ARP round overflows it"

  TARGET[net.ipv4.tcp_max_syn_backlog]=$(( BENCHES * SYN_BACKLOG_PER_BENCH ))
  (( TARGET[net.ipv4.tcp_max_syn_backlog] < 8192 )) && TARGET[net.ipv4.tcp_max_syn_backlog]=8192
  WHY[net.ipv4.tcp_max_syn_backlog]="${SYN_BACKLOG_PER_BENCH} half-open connections per bench x ${BENCHES} benches
# arriving at one proxy, floor 8192"
}

# A knob's running value straight from /proc/sys, or the empty string when this
# kernel does not have it. Never read back from the file we wrote: a file under
# /etc/sysctl.d is a request, not a value.
read_knob() {
  local path="/proc/sys/${1//.//}"
  [[ -r "${path}" ]] || return 0
  awk 'NR==1 {print $1}' "${path}" 2>/dev/null || true
}

proxy_arp_key() { printf 'net.ipv4.conf.%s%s.proxy_arp' "${BRIDGE_DEVICE_PREFIX}" "$1"; }

# One line per knob: verdict, name, running value, target. Writes the names of the
# knobs still below target to $1 so the caller can act on them.
report() {
  local low_file="${1:-/dev/null}" name running verdict threads ceiling
  : >"${low_file}"

  for name in "${KNOBS[@]}"; do
    running="$(read_knob "${name}")"
    if [[ -n "${running}" ]] && (( running >= TARGET[$name] )); then
      verdict="ok "
    else
      verdict="LOW"
      echo "${name}" >>"${low_file}"
    fi
    printf '  %s  %-38s%12s   target %s\n' \
      "${verdict}" "${name}" "${running:--}" "${TARGET[$name]}"
  done

  local index
  for (( index = 0; index < BRIDGES; index++ )); do
    name="$(proxy_arp_key "${index}")"
    running="$(read_knob "${name}")"
    # The bridge does not exist yet, and the family is lazy on purpose.
    [[ -n "${running}" ]] || continue
    if [[ "${running}" == "1" ]]; then
      verdict="ok "
    else
      verdict="LOW"
      echo "${name}" >>"${low_file}"
    fi
    printf '  %s  %-38s%12s   target 1\n' "${verdict}" "${name}" "${running}"
  done

  # Reported, never raised. The quotient is the number an operator needs from it.
  threads="$(read_knob kernel.threads-max)"
  ceiling='-'
  [[ -n "${threads}" ]] && ceiling=$(( threads / BENCH_PIDS_LIMIT ))
  printf '      %-38s%12s   about %s benches at %s pids each, reported and never raised\n' \
    "kernel.threads-max" "${threads:--}" "${ceiling}" "${BENCH_PIDS_LIMIT}"
}

# --- Before -------------------------------------------------------------------

build_knob_table

BEFORE_LOW="$(mktemp)"
AFTER_LOW="$(mktemp)"
trap 'rm -f "${BEFORE_LOW}" "${AFTER_LOW}"' EXIT

log "Sizing for ${BENCHES} benches across ${BRIDGES} bridges. Running values now:"
report "${BEFORE_LOW}"

if [[ ${ASSUME_YES} -eq 0 ]]; then
  cat <<EOF

About to write ${SYSCTL_CONF} with the knobs above marked LOW, and apply it with
\`sysctl --system\`. Nothing is restarted and no container is touched.

Undo: rm ${SYSCTL_CONF} && sysctl --system

EOF
  read -r -p "Proceed? [y/N] " reply
  [[ "${reply}" =~ ^[Yy]$ ]] || die "aborted"
fi

# --- Write --------------------------------------------------------------------
#
# Backed up unconditionally when it exists, so a re-run with different --benches
# leaves the previous sizing recoverable by file rather than by memory.

if [[ -f "${SYSCTL_CONF}" ]]; then
  BACKUP="${SYSCTL_CONF}.$(date -u +%Y%m%dT%H%M%SZ).bak"
  cp -a "${SYSCTL_CONF}" "${BACKUP}"
  log "Backed up ${SYSCTL_CONF} to ${BACKUP}"
fi

log "Rendering ${SYSCTL_CONF}"
mkdir -p "$(dirname "${SYSCTL_CONF}")"

{
  echo "# GENERATED by scripts/tune-host.sh for ${BENCHES} benches across ${BRIDGES} bridges."
  echo "# Do not edit: re-run \`sudo scripts/tune-host.sh\` instead."
  echo "#"
  echo "# Only knobs measured below target are here. Anything absent was already at or"
  echo "# above it and is left to whatever set it."
  echo "#"
  echo "# Undo: remove this file and run \`sysctl --system\`. Every value returns to"
  echo "# whatever the machine image set."
} >"${SYSCTL_CONF}"

WRITTEN=0
while read -r name; do
  # A knob this kernel does not have is skipped rather than written: `sysctl
  # --system` fails on an unknown key, and the gate below reports the absence.
  [[ -n "$(read_knob "${name}")" ]] || continue
  [[ -n "${TARGET[$name]:-}" ]] || continue
  printf '\n# %s\n%s = %s\n' "${WHY[$name]}" "${name}" "${TARGET[$name]}" >>"${SYSCTL_CONF}"
  WRITTEN=$(( WRITTEN + 1 ))
done <"${BEFORE_LOW}"

{
  echo
  echo "# Each bridge answers ARP for its own ports instead of flooding all of them, which is"
  echo "# the O(N^2) storm a full bridge otherwise produces."
  echo "#"
  echo "# The \`-\` prefix means apply if the device exists and do not fail otherwise. Bench"
  echo "# bridges are created lazily, so most of these do not exist at boot; udev's"
  echo "# 99-systemd.rules re-runs systemd-sysctl against net.ipv4.conf.<name> when one is"
  echo "# added, so a bridge created months from now still gets this."
} >>"${SYSCTL_CONF}"

for (( index = 0; index < BRIDGES; index++ )); do
  echo "-$(proxy_arp_key "${index}") = 1" >>"${SYSCTL_CONF}"
done

log "  ${WRITTEN} sysctl knobs written, plus proxy ARP for ${BRIDGES} bridges"

log "Applying"
sysctl --system

# --- The gate -----------------------------------------------------------------
#
# Re-read /proc/sys. The apply exiting 0 says the files parsed, not that the
# values took.

log "Running values after the apply:"
report "${AFTER_LOW}"

if [[ -s "${AFTER_LOW}" ]]; then
  echo
  echo "These knobs are still below target after a successful apply." >&2
  echo "Other files under /etc/sysctl.d naming them, if any:" >&2
  while read -r name; do
    others="$(grep -l -F -- "${name}" /etc/sysctl.conf /etc/sysctl.d/*.conf 2>/dev/null \
              | grep -vF "${SYSCTL_CONF}" || true)"
    printf '  %s: %s\n' "${name}" "${others:-none — the kernel refused the value or the knob is not present}" >&2
  done <"${AFTER_LOW}"
  die "the host is not at target; nothing was rolled back, and ${SYSCTL_CONF} is safe to remove"
fi

log "Every knob is at or above target. Bench containers pick the new limits up on their next start."
