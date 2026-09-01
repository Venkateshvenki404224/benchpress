#!/bin/bash
set -e

# Ralph loop for the public-site rework series.
#
#   ./ralph.sh            # up to 20 iterations
#   ./ralph.sh 5          # up to 5
#
# One fresh Claude session per iteration. It takes the first open, unblocked
# sub-issue of the parent spec, implements only that one, commits, and closes it.
# Progress lives in the GitHub issues and in git, never in a context window.

export IS_SANDBOX=1

# Browser checks. Writes belong on the local stack; production is read-only.
export BP_TEST_URL=${BP_TEST_URL:-https://b3873df7.benchpress.cloud}
export BP_TEST_PASSWORD=${BP_TEST_PASSWORD:-admin}

ITERATIONS=${1:-20}
REPO=/home/ubuntu/benchpress_devops/apps/benchpress
PARENT=288

cd "$REPO"
export PATH="$HOME/.local/bin:$PATH"

stream_text='select(.type == "assistant").message.content[]? | select(.type == "text").text // empty | gsub("\n"; "\r\n") | . + "\r\n\n"'
final_result='select(.type == "result").result // empty'

# Every sub-issue of the parent, with its state and how many blockers are still open.
ticket_status() {
  local slug
  slug=$(gh repo view --json nameWithOwner --jq .nameWithOwner)
  gh api "repos/$slug/issues/$PARENT/sub_issues" --paginate \
    --jq '.[] | "#\(.number) [\(.state)] blocked_by=\(.issue_dependencies_summary.blocked_by // 0) \(.title)"' \
    | sort -t'#' -k2 -n
}

for ((i=1; i<=ITERATIONS; i++)); do
  tmpfile=$(mktemp)
  trap "rm -f $tmpfile" EXIT

  tickets=$(ticket_status)
  commits=$(git log -n 10 --format='%h %ad %s' --date=short)

  echo ""
  echo "===== ralph iteration $i of $ITERATIONS | $(date -u +%H:%M:%SZ) ====="
  echo ""

  claude --dangerously-skip-permissions \
    --verbose \
    --print \
    --output-format stream-json \
    "Ticket status right now:
$tickets

Recent commits on this branch:
$commits

@scripts/prompt.md" \
  | grep --line-buffered '^{' \
  | tee "$tmpfile" \
  | jq --unbuffered -rj "$stream_text"

  result=$(jq -r "$final_result" "$tmpfile")

  if [[ "$result" == *"<promise>COMPLETE</promise>"* ]]; then
    echo ""
    echo "Ralph complete after $i iterations. All tickets done."
    exit 0
  fi
done

echo ""
echo "Ralph stopped: $ITERATIONS iterations without COMPLETE."
exit 1
