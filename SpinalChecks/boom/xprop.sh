#!/usr/bin/env bash
# BOOM X-propagation from reset: can any Stream/Flow valid (from the checks report) be X after reset?
# Uses the Verilog and report written by from-sim.sh / run-suite.sh. Takes the machine-wide boom lock.
#   SpinalChecks/boom/xprop.sh [outDir] [depth] [extra rvw args...]
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
out="${1:-out/fs2-small}"; depth="${2:-8}"; shift 2 || true
: "${ENV_SH:?Set ENV_SH to the BOOM environment setup script}"
[ -f "$ENV_SH" ] || { echo "ENV_SH is not a file: $ENV_SH" >&2; exit 2; }
source "$ENV_SH"
cd "$here"
rtl=$(ls $out/sim/*/rtl/*.v | head -1)
exec "$here/../../scripts/with-lock.sh" boom /usr/bin/time -l "$here/../../rvw/.venv/bin/rvw" formal xprop \
  --verilog "$rtl" --top BoomSimTop --checks "$out/BoomSimTop.checks.json" --reset-cycles 2 --depth "$depth" \
  --timeout "${TIMEOUT:-3600}" --out "$out/xprop-d$depth" "$@"
