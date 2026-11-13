#!/usr/bin/env bash
# rvw query build entry: build-db.sh rv32imasu OUT [SpinalDB options]
set -euo pipefail
[ "$#" -ge 2 ] && [ "$1" = rv32imasu ] || {
  echo 'usage: build-db.sh rv32imasu OUT [SpinalDB options]' >&2; exit 2;
}
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export RVW_HOME="$(cd "${RVW_HOME:?Set RVW_HOME to the installed workstation checkout.}" && pwd)"
export NAXRISCV="$(cd "${NAXRISCV:-$here/..}" && pwd)"
export RVW_SPINAL_SOURCE="$NAXRISCV/ext/SpinalHDL"
export RVW_ADAPTER="$here"
export SPINALDB_PROCESS_RUNNER="$RVW_HOME/SpinalDB/scripts/hdl-deps.py"
export SPINALDB_PYTHON="${RVW_PYTHON:-$RVW_HOME/rvw/.venv/bin/python}"
export RVW_LOCK_PYTHON="${RVW_LOCK_PYTHON:-$RVW_HOME/rvw/.venv/bin/python}"
mkdir -p "$(dirname "$2")"
out="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"
argsdir="$(mktemp -d /tmp/rvw-nax-db.XXXXXX)"
trap 'rm -rf "$argsdir"' EXIT
config="$1"; shift 2
printf '%s\0' "$config" "$out" "$@" > "$argsdir/args"
cd "$here"
"$RVW_HOME/scripts/with-lock.sh" "${RVW_NAX_LOCK:-nax}" "$RVW_HOME/scripts/with-lock.sh" "${RVW_NAX_SBT_LOCK:-sbt-nax}" \
  nice -n 10 sbt -J-Xmx4g -batch -Dsbt.offline=true '++2.12.18!' "db/runMain rvwnax.Database --args-file $argsdir/args"
