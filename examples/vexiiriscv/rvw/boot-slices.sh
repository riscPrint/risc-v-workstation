#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="${RVW_HOME:?Set RVW_HOME}"
if [[ "${1:-}" != --locked ]]; then
  exec "$repo/scripts/with-lock.sh" vex-linux nice -n 10 "$BASH" "$0" --locked "$@"
fi
shift
export SPINAL_MAKE_CMD="$repo/RiscvSim/scripts/make-jobs.sh"
export VEXIIRISCV="${VEXIIRISCV:?Set VEXIIRISCV to a private core copy}"
output="$(cd "$here" && "$repo/scripts/with-lock.sh" sbt-linux nice -n 10 sbt -J-Xmx3g -batch \
  '++2.13.14!' 'root/compile' 'export root/Runtime/fullClasspath' 2>&1)" || { echo "$output" >&2; exit 2; }
cp="$(printf '%s\n' "$output" | grep -v '^\[' | grep scala-library | tail -1)"
[[ -n "$cp" ]] || { echo "$output" >&2; exit 2; }
exec nice -n 10 java -Xss64m -Xmx3g -XX:+UseParallelGC -Driscvsim.script="$here/run.sh" -cp "$cp" rvwvexii.BootSlices "$@"
