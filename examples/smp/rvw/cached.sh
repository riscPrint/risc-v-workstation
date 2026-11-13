#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
if [ "${1:-}" != --locked ]; then
  exec "$repo/scripts/with-lock.sh" vex-mem nice -n 10 "$BASH" "$0" --locked "$@"
fi
shift
export RVW_HOME="$repo"
export SPINAL_MAKE_CMD="$repo/RiscvSim/scripts/make-jobs.sh"
: "${VEXIIRISCV:?Set VEXIIRISCV to the private pinned core copy}"
elf="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
mkdir -p "$2"
out="$(cd "$2" && pwd)"
cd "$here"
exec "$repo/scripts/with-lock.sh" sbt-mem nice -n 10 sbt -J-Xmx3g -batch -Dsbt.offline=true \
  '++2.13.14!' "runMain rvwsmp.CachedSmpMain $elf $out"
