#!/usr/bin/env bash
# The repo's checks. Exit 0 only when the branch is fit to review.
#
# The gate runs this script from the main checkout with the job's worktree as
# the working directory. Keep it fast, deterministic and non-interactive: no
# watch modes, no prompts, nothing that rewrites files.
#
# BenchPress: the lint, frontend and docs jobs from .github/workflows. The
# server suite needs a bench and a site, so it runs only in CI, and
# `factory/bin/job merge` waits for the PR's checks before it merges.
set -euo pipefail

factory=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
base=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["base_branch"])' "$factory/config.json")
yarn=(npx --yes yarn@1.22.22)

# pre-commit's ruff and prettier hooks fix files in place. On a clean tree,
# put them back afterwards; on a dirty one, pre-commit rolls its fixes back itself.
if [ -z "$(git status --porcelain)" ]; then
	trap 'git checkout -q -- . && git clean -fdq -- docs-site docs-bundle' EXIT
fi

echo "== pre-commit"
uvx pre-commit@4.3.0 run --all-files --show-diff-on-failure

echo "== frontend"
(
	cd frontend
	"${yarn[@]}" install --frozen-lockfile --network-timeout 600000 --silent
	"${yarn[@]}" test:run
	"${yarn[@]}" build
)

if git diff --name-only "origin/$base...HEAD" | grep -qE '^(docs|docs-site|docs-bundle)/|^package(-lock)?\.json$'; then
	echo "== docs"
	npm ci --ignore-scripts --silent
	npm run docs:build
	npm run docs:lint
	npm run docs:score
	if [ -n "$(git status --porcelain -- docs-site docs-bundle)" ]; then
		echo "docs-site/ or docs-bundle/ is stale or hand-edited. Run npm run docs:build and commit the result." >&2
		git status --porcelain -- docs-site docs-bundle >&2
		exit 1
	fi
fi
