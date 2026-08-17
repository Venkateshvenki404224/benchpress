#!/usr/bin/env bash
#
# Regenerates THIRD-PARTY-NOTICES.md from the installed dependency tree.
#
# The file is generated, never hand-edited: the published container image
# redistributes third-party Python wheels and the built frontend bundle inlines
# third-party JavaScript, so the notice list has to track what is actually
# shipped rather than what someone remembered to write down.
#
# Run it inside the bench (the Python side reads the bench virtualenv):
#
#   docker compose exec backend bash -lc \
#     'cd apps/benchpress && ./scripts/generate-third-party-notices.sh'
#
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT="${APP_DIR}/THIRD-PARTY-NOTICES.md"

# Standard bench layout: apps/<app>/../../env is the bench virtualenv.
BENCH_PYTHON="${BENCH_PYTHON:-${APP_DIR}/../../env/bin/python}"

# pip-licenses and prettytable are reporting tooling, not shipped dependencies.
REPORTING_ONLY="pip-licenses prettytable"

# The apps themselves are covered by license.txt, not by a third-party notice.
FIRST_PARTY="benchpress vpn_management"

require_bench_python() {
	if [ ! -x "${BENCH_PYTHON}" ]; then
		echo "No bench virtualenv at ${BENCH_PYTHON}." >&2
		echo "Run this inside the bench, or set BENCH_PYTHON." >&2
		exit 1
	fi
}

python_notices() {
	"${BENCH_PYTHON}" -m pip install --quiet pip-licenses
	"${BENCH_PYTHON}" -m piplicenses \
		--format=markdown \
		--order=license \
		--with-urls \
		--ignore-packages ${REPORTING_ONLY} ${FIRST_PARTY}
	"${BENCH_PYTHON}" -m pip uninstall --quiet --yes ${REPORTING_ONLY}
}

# Frappe's container images install node through nvm, which a non-interactive
# shell does not put on PATH.
load_node() {
	if ! command -v npx >/dev/null && [ -s "${HOME}/.nvm/nvm.sh" ]; then
		# shellcheck disable=SC1091
		. "${HOME}/.nvm/nvm.sh"
	fi
}

javascript_notices() {
	load_node
	# --excludePrivatePackages drops our own frontend package, which is the only
	# private one in a production tree.
	(cd "${APP_DIR}/frontend" &&
		npx --yes license-checker-rseidelsohn --production --markdown --excludePrivatePackages)
}

write_header() {
	cat <<'HEADER'
# Third-party notices

BenchPress is distributed under the GNU Affero General Public License v3.0 only
(see [license.txt](license.txt)). It bundles and redistributes the third-party
components listed below, each under its own license.

**This file is generated — do not edit it by hand.** Regenerate it with
`./scripts/generate-third-party-notices.sh` whenever a dependency is added,
removed, or upgraded.

The full license text of every component is shipped alongside the component
itself: Python packages carry theirs in `env/lib/python*/site-packages/*.dist-info/`
inside the published container image, and JavaScript packages carry theirs in
`node_modules/*/LICENSE`. To produce a single bundle of the full texts, run
`pip-licenses --format=markdown --with-license-file` in the bench virtualenv.

Frappe apps BenchPress integrates with — razorpay_frappe, vpn_management — are not dependency
metadata and are documented by hand in
[docs/integration-notices.md](docs/integration-notices.md).

HEADER
}

# A handful of upstreams publish no license metadata, or publish a stray extra
# classifier, so the generated tables above report the wrong thing for them.
# Each correction below was read out of the shipped license file itself.
write_corrections() {
	cat <<'CORRECTIONS'

## Metadata corrections

The tables above report what each package publishes in its own metadata. Two
upstreams publish something incomplete or misleading; the authoritative license
is the one in the license file each of them actually ships.

| Package | Reported above | Actual license | Source |
|---|---|---|---|
| `frappe` | UNKNOWN — publishes no license metadata | MIT | `apps/frappe/LICENSE` |
| `qrcode` | `BSD License; Other/Proprietary License` | BSD 3-Clause | `qrcode-*.dist-info/LICENSE` |
CORRECTIONS
}

require_bench_python

{
	write_header
	echo "## Python dependencies"
	echo
	python_notices
	echo
	echo "## JavaScript dependencies (frontend, production only)"
	echo
	javascript_notices
	write_corrections
} >"${OUTPUT}"

echo "Wrote ${OUTPUT}"
