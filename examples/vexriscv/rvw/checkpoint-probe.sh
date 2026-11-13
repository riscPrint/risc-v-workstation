#!/usr/bin/env bash
# Project-owned live bridge probe. Hold vex across elaboration and native execution.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="${RVW_HOME:?Set RVW_HOME}"
if [[ "${1:-}" != --locked ]]; then
  exec "$repo/scripts/with-lock.sh" "${RVW_VEX_LOCK:-vex}" "$BASH" "$0" --locked "$@"
fi
shift
export SPINAL_MAKE_CMD="$repo/RiscvSim/scripts/make-jobs.sh"
export VEXRISCV="${VEXRISCV:-$here/..}"
mkdir -p "$2"
build_log="$(cd "$2" && pwd)/sbt-build.log"
output="$(cd "$here" && "$repo/scripts/with-lock.sh" "${RVW_SBT_LOCK:-sbt}" nice -n 10 sbt -batch \
  compile 'export Runtime/fullClasspath' 2>&1 | tee "$build_log")" || { echo "$output" >&2; exit 2; }
cp="$(printf '%s\n' "$output" | grep -v '^\[' | grep scala-library | tail -1)"
[[ -n "$cp" ]] || { echo "$output" >&2; exit 2; }
exec nice -n 10 java -Xmx3g -cp "$cp" rvwvex.CheckpointProbe "$@"
