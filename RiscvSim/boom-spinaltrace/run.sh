#!/usr/bin/env bash
# BOOM run contract (C1) with a SpinalTrace-instrumented model. Same options as ../boom/run.sh;
# result.json gets details.pdg. Runs through sbt (slower start than ../boom/run.sh).
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
export RVW_PYTHON="${RVW_PYTHON:-$repo/rvw/.venv/bin/python}"
if [[ "$RVW_PYTHON" != /* ]] || [ ! -x "$RVW_PYTHON" ]; then
  echo "[run.sh] set RVW_PYTHON to an absolute Python interpreter, or create $repo/rvw/.venv" >&2
  exit 2
fi
if [ "${1:-}" = --riscvsim-supervised ]; then
  shift 2
else
  exec "$RVW_PYTHON" "$repo/RiscvSim/scripts/supervise.py" "$BASH" "$here/run.sh" "$@"
fi
boom="$(cd "${SPINAL_BOOM:-$repo/../spinal-boom-eda}" && pwd)"
export SPINAL_BOOM="$boom"
if [ -z "${JAVA_HOME:-}" ] && [ -f "$boom/env.sh" ]; then source "$boom/env.sh"; fi
command -v verilator >/dev/null || { echo "[run.sh] add Verilator to PATH" >&2; exit 2; }
export SPINALTRACE_NONINTERACTIVE=1
# sbt and Scala string quoting (not bash's printf %q): wrap in double quotes, escape \ and ".
# Used for the runMain arguments and for the paths inside the `set` commands, so paths and
# arguments with spaces, quotes or backslashes reach the JVM unchanged.
q() { local s=${1//\\/\\\\}; s=${s//\"/\\\"}; printf '"%s"' "$s"; }
args=""
for a in "$@"; do args+=" $(q "$a")"; done
caller="$PWD"
cd "$here"
exec sbt -J-Xmx4g -batch -error \
  "set run / fork := true" \
  "set run / outputStrategy := Some(StdoutOutput)" \
  "set run / javaOptions ++= Seq(\"-Xss64m\", $(q "-Xmx${RISCVSIM_XMX:-16g}"), \"-XX:+UseParallelGC\", $(q "-Driscvsim.cwd=$caller"), $(q "-Driscvsim.script=$here/run.sh"), $(q "-Driscvsim.boom.dir=$boom"), $(q "-Driscvsim.tools=$repo"))" \
  "set run / baseDirectory := file($(q "$boom"))" \
  "runMain riscvsim.boomtrace.Main$args"
