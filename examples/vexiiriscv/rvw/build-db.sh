#!/usr/bin/env bash
set -euo pipefail
[ "$#" -ge 2 ] && [ "$1" = rv32im ] || {
  echo 'usage: build-db.sh rv32im OUT [SpinalDB options]' >&2; exit 2;
}
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export RVW_HOME="$(cd "${RVW_HOME:?Set RVW_HOME to the installed workstation checkout.}" && pwd)"
export VEXIIRISCV="$(cd "${VEXIIRISCV:-$here/..}" && pwd)"
export RVW_ADAPTER="$here"
export SPINALDB_PROCESS_RUNNER="$RVW_HOME/SpinalDB/scripts/hdl-deps.py"
export SPINALDB_PYTHON="${RVW_PYTHON:-$RVW_HOME/rvw/.venv/bin/python}"
export RVW_LOCK_PYTHON="${RVW_LOCK_PYTHON:-$RVW_HOME/rvw/.venv/bin/python}"
mkdir -p "$(dirname "$2")"
out="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"
argsdir="$(mktemp -d /tmp/rvw-vexii-db.XXXXXX)"
trap 'rm -rf "$argsdir"' EXIT
config="$1"; shift 2
printf '%s\0' "$config" "$out" "$@" > "$argsdir/args"
cd "$here"
"$RVW_HOME/scripts/with-lock.sh" vex "$RVW_HOME/scripts/with-lock.sh" sbt \
  nice -n 10 sbt -J-Xmx3g -batch -Dsbt.offline=true '++2.13.14!' "db/runMain rvwvexii.Database --args-file $argsdir/args"
