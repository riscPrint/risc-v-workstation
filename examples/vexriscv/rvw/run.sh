#!/usr/bin/env bash
# C1 launcher. Reuse the generic supervisor, source identity and native tool capture.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "${RVW_HOME:?Set RVW_HOME to the installed workstation checkout.}" && pwd)"
sim="$repo/RiscvSim"
export RVW_PYTHON="${RVW_PYTHON:-$repo/rvw/.venv/bin/python}"
if [[ "$RVW_PYTHON" != /* ]] || [ ! -x "$RVW_PYTHON" ]; then
  echo 'Set RVW_PYTHON to an absolute Python interpreter with rvw installed.' >&2
  exit 2
fi
if [ "${1:-}" = --riscvsim-supervised ]; then
  launch_owner="$2"; shift 2
else
  exec "$RVW_PYTHON" "$sim/scripts/supervise.py" "$BASH" "$here/run.sh" "$@"
fi
export RVW_LOCK_PYTHON="$RVW_PYTHON"
if [ "${1:-}" = --vex-locked ]; then
  shift
else
  exec "$repo/scripts/with-lock.sh" "${RVW_VEX_LOCK:-vex}" "$BASH" "$here/run.sh" \
    --riscvsim-supervised "$launch_owner" --vex-locked "$@"
fi
trap 'exit 143' TERM
trap 'exit 130' INT
trap 'exit 129' HUP
export VEXRISCV="$(cd "${VEXRISCV:-$here/..}" && pwd)"
if [ -n "${RISCVSIM_EXTRA_INPUTS:-}" ]; then
  echo 'input_not_captured:custom_build_layout' >&2
  exit 2
fi
export SPINAL_MAKE_CMD="$sim/scripts/make-jobs.sh"
native_identity="$("$RVW_PYTHON" "$sim/scripts/native-identity.py")"
if [ "${1:-}" = identity ] && [[ "$native_identity" = *'"cache_enabled":false'* ]]; then
  echo 'Native inputs unavailable; refusing identity for result reuse.' >&2
  exit 2
fi
"$RVW_PYTHON" "$sim/scripts/source-identity.py" "$VEXRISCV" "$repo" > "$launch_owner/source.json"
output="$(cd "$here" && "$repo/scripts/with-lock.sh" "${RVW_SBT_LOCK:-sbt}" nice -n 10 \
  sbt -J-Xmx3g -batch -Dsbt.offline=true 'root/compile' 'export root/Runtime/fullClasspath' 2>&1)" || {
  echo "$output" >&2; exit 2;
}
cp="$(printf '%s\n' "$output" | grep -v '^\[' | grep 'scala-library' | tail -1)"
if [ -z "$cp" ]; then echo "$output" >&2; echo 'No classpath in sbt output.' >&2; exit 2; fi
exec "$RVW_PYTHON" "$sim/scripts/native-identity.py" launch "$native_identity" "$launch_owner" \
  -Xss64m -Xmx"${RISCVSIM_XMX:-3g}" -XX:+UseParallelGC \
  -Driscvsim.cwd="$PWD" -Driscvsim.script="$here/run.sh" \
  -Driscvsim.tools="$repo" -Driscvsim.source="$launch_owner/source.json" \
  -cp "$cp" rvwvex.Main "$@"
