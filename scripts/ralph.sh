#!/bin/bash
# Work the open sub-issues of a parent spec issue, one fresh Claude session each,
# in dependency order. Built to run unattended.
set -uo pipefail

PARENT=${PARENT:-288}
BASE_BRANCH=${BASE_BRANCH:-feat/public-site}
REPO_ROOT=$(git rev-parse --show-toplevel)
LOG_DIR="$REPO_ROOT/.ralph/$(date +%Y%m%d-%H%M%S)"
MAX_ATTEMPTS=${MAX_ATTEMPTS:-2}
PUSH=0
DRY_RUN=0

usage() { echo "Usage: $0 <max-iterations> [--push] [--dry-run]"; exit 1; }
[ $# -ge 1 ] || usage
ITERATIONS=$1; shift
for a in "$@"; do
  case "$a" in
    --push) PUSH=1 ;;
    --dry-run) DRY_RUN=1 ;;
    *) usage ;;
  esac
done

cd "$REPO_ROOT"

# nohup/cron shells do not source a profile, and every tool below lives here.
export PATH="$HOME/.local/bin:$PATH"

# Browser checks run against this. Override either to point somewhere else or to
# rotate the password without a commit.
export BP_TEST_URL=${BP_TEST_URL:-https://b3873df7.benchpress.cloud}
export BP_TEST_PASSWORD=${BP_TEST_PASSWORD:-admin}
for tool in claude gh jq docker uvx; do
  command -v "$tool" >/dev/null || { echo "ralph: $tool not found on PATH"; exit 1; }
done

REPO=$(gh repo view --json nameWithOwner --jq .nameWithOwner)

declare -A ATTEMPTS

log() { printf '\n\033[1;34m[ralph %s]\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }
fail() { printf '\n\033[1;31m[ralph %s]\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }

# Open sub-issues of PARENT whose blockers are all closed, lowest number first.
frontier() {
  local n blocked
  for n in $(gh api "repos/$REPO/issues/$PARENT/sub_issues" --paginate \
               --jq '.[] | select(.state=="open") | .number' 2>/dev/null | sort -n); do
    [ "${ATTEMPTS[$n]:-0}" -ge "$MAX_ATTEMPTS" ] && continue
    blocked=$(gh api "repos/$REPO/issues/$n" --jq '.issue_dependencies_summary.blocked_by // 0' 2>/dev/null)
    [ "${blocked:-0}" -eq 0 ] && echo "$n"
  done
}

open_count() {
  gh api "repos/$REPO/issues/$PARENT/sub_issues" --paginate \
    --jq '[.[] | select(.state=="open")] | length' 2>/dev/null
}

if [ "$DRY_RUN" -eq 1 ]; then
  log "parent #$PARENT on $REPO | base branch $BASE_BRANCH"
  log "open sub-issues: $(open_count)"
  log "frontier (ready to start now):"
  for n in $(frontier); do
    printf '  #%s  %s\n' "$n" "$(gh issue view "$n" --json title --jq .title)"
  done
  exit 0
fi

mkdir -p "$LOG_DIR"
log "logging to $LOG_DIR"

# A dirty tree from a previous run poisons every session after it.
if [ -n "$(git status --porcelain)" ]; then
  fail "working tree is dirty. Commit or stash before starting."
  exit 1
fi
if [ "$(git rev-parse --abbrev-ref HEAD)" != "$BASE_BRANCH" ]; then
  log "switching to $BASE_BRANCH"
  git checkout "$BASE_BRANCH" || { fail "cannot check out $BASE_BRANCH"; exit 1; }
fi

STREAM_TEXT='select(.type == "assistant").message.content[]? | select(.type == "text").text // empty | gsub("\n"; "\r\n") | . + "\r\n\n"'
FINAL_RESULT='select(.type == "result").result // empty'

for ((i = 1; i <= ITERATIONS; i++)); do
  mapfile -t READY < <(frontier)
  if [ ${#READY[@]} -eq 0 ]; then
    if [ "$(open_count)" -eq 0 ]; then
      log "every sub-issue of #$PARENT is closed. Done after $((i - 1)) iterations."
      exit 0
    fi
    fail "nothing startable: remaining issues are blocked or hit the attempt limit."
    gh issue list --state open --json number,title --jq '.[] | "  #\(.number)  \(.title)"' 2>/dev/null
    exit 1
  fi

  N=${READY[0]}
  ATTEMPTS[$N]=$(( ${ATTEMPTS[$N]:-0} + 1 ))
  TITLE=$(gh issue view "$N" --json title --jq .title)
  log "iteration $i/$ITERATIONS -> #$N (attempt ${ATTEMPTS[$N]}): $TITLE"

  BEFORE=$(git rev-parse HEAD)
  BODY=$(gh issue view "$N" --json number,title,body,comments)
  TMP=$(mktemp)

  PROMPT="/implement GitHub issue #$N in this repository. Implement only this issue.

$BODY

Follow the rules in @scripts/prompt.md exactly."

  claude --dangerously-skip-permissions \
    --verbose --print --output-format stream-json \
    "$PROMPT" \
    | grep --line-buffered '^{' \
    | tee "$TMP" \
    | jq --unbuffered -rj "$STREAM_TEXT"

  cp "$TMP" "$LOG_DIR/issue-$N-attempt-${ATTEMPTS[$N]}.jsonl"
  RESULT=$(jq -r "$FINAL_RESULT" "$TMP" 2>/dev/null)
  rm -f "$TMP"
  AFTER=$(git rev-parse HEAD)

  if [[ "$RESULT" != *"<promise>COMPLETE</promise>"* ]]; then
    fail "#$N did not report completion. Leaving it open."
  elif [ "$BEFORE" = "$AFTER" ]; then
    fail "#$N reported completion but committed nothing. Leaving it open."
  elif [ -n "$(git status --porcelain)" ]; then
    fail "#$N left the tree dirty. Leaving it open and stopping."
    exit 1
  else
    log "#$N done: $(git log --oneline "$BEFORE..$AFTER" | wc -l) commit(s)"
    gh issue close "$N" --comment "Implemented by an unattended run. Commits: \`$(git rev-parse --short "$BEFORE")..$(git rev-parse --short "$AFTER")\` on \`$BASE_BRANCH\`." >/dev/null 2>&1 \
      && log "#$N closed"
    [ "$PUSH" -eq 1 ] && { git push origin "$BASE_BRANCH" >/dev/null 2>&1 && log "pushed $BASE_BRANCH"; }
  fi

  # Never carry a half-finished tree into the next session.
  if [ -n "$(git status --porcelain)" ]; then
    fail "tree dirty after #$N. Stopping so the next session is not poisoned."
    git status --short
    exit 1
  fi
done

log "ran $ITERATIONS iterations. $(open_count) sub-issue(s) still open."
