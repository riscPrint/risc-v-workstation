#!/usr/bin/env bash
# Generate plain VexiiRiscv Verilog for `rvw sec` native runs: build-rtl.sh OUT [config...]
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export RVW_HOME="$(cd "${RVW_HOME:?Set RVW_HOME to the installed workstation checkout.}" && pwd)"
export VEXIIRISCV="$(cd "${VEXIIRISCV:-$here/..}" && pwd)"
export RVW_LOCK_PYTHON="${RVW_LOCK_PYTHON:-$RVW_HOME/rvw/.venv/bin/python}"
mkdir -p "$1"; out="$(cd "$1" && pwd)"; shift
cd "$here"
"$RVW_HOME/scripts/with-lock.sh" "${RVW_VEX_LOCK:-vex}" "$RVW_HOME/scripts/with-lock.sh" "${RVW_SBT_LOCK:-sbt}" \
  nice -n 10 sbt -J-Xmx3g -batch -Dsbt.offline=true '++2.13.14!' "root/runMain rvwvexii.SecRtl $out $*"
