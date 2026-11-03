#!/usr/bin/env bash
# BOOM run-contract adapter. Each launch uses sbt's incremental compiler offline.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/.." && pwd)"
repo="$(cd "$root/.." && pwd)"
python_default="$repo/rvw/.venv/bin/python"
[ -x "$python_default" ] || python_default="$repo/.venv/bin/python"
export RVW_PYTHON="${RVW_PYTHON:-$python_default}"
if [[ "$RVW_PYTHON" != /* ]] || [ ! -x "$RVW_PYTHON" ]; then
  echo "[run.sh] set RVW_PYTHON to an absolute Python interpreter, or create $repo/.venv" >&2
  exit 2
fi
if [ "${1:-}" = --riscvsim-supervised ]; then
  launch_owner="$2"; shift 2
else
  exec "$RVW_PYTHON" "$root/scripts/supervise.py" "$BASH" "$here/run.sh" "$@"
fi
# The JVM reads sbt's output directories. Keep the lock until it exits so another
# launch cannot recompile those classes while this JVM loads them.
if [ "${1:-}" = --riscvsim-locked ]; then
  shift
elif [ -z "${RVW_NO_LOCK:-}" ]; then
  export RVW_LOCK_PYTHON="$RVW_PYTHON"
  exec "$repo/scripts/with-lock.sh" boom "$BASH" "$here/run.sh" \
    --riscvsim-supervised "$launch_owner" --riscvsim-locked "$@"
fi
trap 'exit 143' TERM
trap 'exit 130' INT
trap 'exit 129' HUP
export RVW_LOCK_PYTHON="$RVW_PYTHON"
boom="$(cd "${SPINAL_BOOM:-$root/../../spinal-boom-eda}" && pwd)"
export SPINAL_BOOM="$boom"
if [ -z "${JAVA_HOME:-}" ] && [ -f "$boom/env.sh" ]; then source "$boom/env.sh"; fi
command -v verilator >/dev/null || { echo "[run.sh] add Verilator to PATH" >&2; exit 2; }
if [ -n "${RISCVSIM_EXTRA_INPUTS:-}" ]; then
  echo "input_not_captured:custom_build_layout" >&2
  exit 2
fi
export SPINAL_MAKE_CMD="$root/scripts/make-jobs.sh"
native_identity="$("$RVW_PYTHON" "$root/scripts/native-identity.py")"
if [ "${1:-}" = identity ] && [[ "$native_identity" = *'"cache_enabled":false'* ]]; then
  echo '[run.sh] native inputs unavailable; refusing identity for result reuse' >&2
  exit 2
fi
# Record revisions before compilation. RTL, not the sbt classpath, identifies the design.
"$RVW_PYTHON" "$root/scripts/source-identity.py" "$boom" "$repo" > "$launch_owner/source.json"
sbt_cmd=(sbt -J-Xmx4g -batch -Dsbt.offline=true "boom/compile" "export boom/Runtime/fullClasspath")
output="$(cd "$here" && "$repo/scripts/with-lock.sh" sbt "${sbt_cmd[@]}" 2>&1)" || { echo "$output" >&2; exit 2; }
cp="$(printf '%s\n' "$output" | grep -v '^\[' | grep 'scala-library' | tail -1)"
if [ -z "$cp" ]; then echo "$output" >&2; echo '[run.sh] no classpath in sbt output' >&2; exit 2; fi
# The supervisor owns temporary metadata until all child processes stop.
exec "$RVW_PYTHON" "$root/scripts/native-identity.py" launch "$native_identity" "$launch_owner" \
  -Xss64m -Xmx"${RISCVSIM_XMX:-8g}" -XX:+UseParallelGC \
  -Driscvsim.cwd="$PWD" -Driscvsim.script="$here/run.sh" -Driscvsim.boom.dir="$boom" \
  -Driscvsim.tools="$repo" -Driscvsim.source="$launch_owner/source.json" \
  -cp "$cp" riscvsim.boom.Main "$@"
