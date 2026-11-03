#!/usr/bin/env bash
# Run from the repository root. This script takes the shared heavy-job lock itself.
set -euo pipefail
repo=$(cd "$(dirname "$0")/../../.." && pwd)
out=${1:?usage: collect-boom.sh OUT_DIR}
cd "$repo"
: "${SPINAL_BOOM:?Set SPINAL_BOOM to a separate BOOM source checkout}"
[ -d "$SPINAL_BOOM" ] || { echo "SPINAL_BOOM is not a directory: $SPINAL_BOOM" >&2; exit 2; }
export SPINAL_BOOM
export RISCVSIM_KEEP_WS=1
# Verilator 5.049's experimental FSM detector crashes on BOOM's empty reset branches.
# Keep line/branch/toggle/expression/user coverage, and record this in each C1 model/replay.
# RiscvSim selects FSM coverage through its native Verilator version gate.
# Set RISCVSIM_COVERAGE explicitly to reproduce a historical point universe.
export JAVA_TOOL_OPTIONS="${JAVA_TOOL_OPTIONS:-} -XX:ActiveProcessorCount=4"
# Outer lock covers the adapter's sbt bootstrap, compile, Verilator and simulations.
scripts/with-lock.sh boom rvw/.venv/bin/rvw regress run \
  --core rvw/examples/coverage/boom.toml --suite integer-coverage --config small \
  --source "$SPINAL_BOOM" --out "$out" --jobs 1 --no-cache --no-index --json
