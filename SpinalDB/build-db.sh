#!/usr/bin/env bash
# Build a design database (rvw.designdb/20).
#
#   SpinalDB/build-db.sh class TOP_CLASS OUT.db [--sbt-dir DIR] [--test] [spinaldb options]
#       any component with a no-argument constructor, run from the sbt project DIR (default
#       SpinalDB/spinaldb; the project must depend on spinaldb). --test uses the Test classpath.
#   SpinalDB/build-db.sh ENTRY CONFIG OUT.db [spinaldb options]
#       a named entry: the sbt build in SpinalDB/ENTRY/, whose `run CONFIG OUT [options]` writes
#       the database. SpinalDB/ENTRY/entry.sh sets its environment and LOCK (the machine-wide
#       lock to hold, if any). `boom`: spinal-boom's BoomSimTop (CONFIG: small, medium, large,
#       mega, giga) from $SPINAL_BOOM, holding the `boom` lock.
#
# spinaldb options: --rtl DIR, --source-root DIR (repeatable), --no-pdg, --pdg-tables, --no-blocks,
# --no-hgldd, --meta KEY=VALUE. JDK and sbt must be on PATH (`source spinal-boom/env.sh`).
#
# Arguments reach the JVM through a NUL-separated file (`--args-file`), never through sbt's command
# parser, so paths with spaces, quotes or `;` are passed as they are.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(dirname "$here")"
abs() { mkdir -p "$(dirname "$1")"; echo "$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"; }

[ $# -ge 3 ] || { sed -n '2,17p' "$0"; exit 2; }
mode="$1"; shift

argsdir="$(mktemp -d /tmp/spinaldb-args.XXXXXX)"
trap 'rm -rf "$argsdir"' EXIT
argsfile="$argsdir/args"
write_args() { : > "$argsfile"; for a in "$@"; do printf '%s\0' "$a" >> "$argsfile"; done; }

case "$mode" in
  class)
    top="$1"; out="$(abs "$2")"; shift 2
    dir="$here/spinaldb"; task="runMain"; rest=()
    while [ $# -gt 0 ]; do
      case "$1" in
        --sbt-dir) dir="$2"; shift 2 ;;
        --test) task="Test/runMain"; shift ;;
        *) rest+=("$1"); shift ;;
      esac
    done
    write_args "$top" "$out" ${rest[@]+"${rest[@]}"}
    cd "$dir"
    sbt -J-Xmx4g -batch "$task spinaldb.Main --args-file $argsfile"
    ;;
  *)
    case "$mode" in *[!A-Za-z0-9_-]*|"") echo "bad entry name: $mode" >&2; exit 2 ;; esac
    entry="$here/$mode"
    [ -f "$entry/entry.sh" ] && [ -f "$entry/build.sbt" ] || {
      echo "unknown entry $mode (class, or a directory SpinalDB/<entry> with build.sbt and entry.sh)" >&2; exit 2; }
    config="$1"; out="$(abs "$2")"; shift 2
    LOCK=""
    # shellcheck source=/dev/null
    . "$entry/entry.sh"
    write_args "$config" "$out" "$@"
    cd "$entry"
    if [ -n "$LOCK" ]; then
      "$root/scripts/with-lock.sh" "$LOCK" sbt -J-Xmx4g -batch "run --args-file $argsfile"
    else
      sbt -J-Xmx4g -batch "run --args-file $argsfile"
    fi
    ;;
esac
