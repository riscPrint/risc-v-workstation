#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="${RVW_HOME:?Set RVW_HOME}"
if [[ "${1:-}" != --locked ]]; then
  exec "$repo/scripts/with-lock.sh" vex-linux "$BASH" "$0" --locked "$@"
fi
shift
# nice takes an increment. Reach priority 10 once, including under a nice parent.
priority="$(ps -o ni= -p "$$")"
priority="${priority//[[:space:]]/}"
[[ "$priority" =~ ^-?[0-9]+$ ]] || { echo 'Cannot read process niceness.' >&2; exit 2; }
nice_delta=$((priority < 10 ? 10 - priority : 0))
opt="${RVW_BOOT_OPT:-3}"
threads="${RVW_BOOT_THREADS:-1}"
[[ "$opt" =~ ^[0-3]$ ]] || { echo 'RVW_BOOT_OPT must be 0..3.' >&2; exit 2; }
[[ "$threads" =~ ^[1-9][0-9]*$ ]] && (( threads <= 64 )) || { echo 'RVW_BOOT_THREADS must be 1..64.' >&2; exit 2; }
[[ ! "${SPINAL_VERILATOR_FLAGS:-}" =~ (^|[[:space:]])--threads(=|[[:space:]]) ]] || { echo 'Select threads with RVW_BOOT_THREADS.' >&2; exit 2; }
export SPINAL_VERILATOR_FLAGS="${SPINAL_VERILATOR_FLAGS:-} -CFLAGS -O$opt --threads $threads"
export SPINAL_MAKE_CMD="$repo/RiscvSim/scripts/make-jobs.sh"
export VEXIIRISCV="${VEXIIRISCV:?Set VEXIIRISCV to a private core copy}"
if [[ -n "${RVW_BOOT_CLASSPATH:-}" ]]; then
  cp="$(cat "$RVW_BOOT_CLASSPATH")"
else
output="$(cd "$here" && "$repo/scripts/with-lock.sh" sbt-linux nice -n "$nice_delta" sbt -J-Xmx3g -batch \
  '++2.13.14!' 'root/compile' 'export root/Runtime/fullClasspath' 2>&1)" || { echo "$output" >&2; exit 2; }
cp="$(printf '%s\n' "$output" | grep -v '^\[' | grep scala-library | tail -1)"
fi
if [[ -n "${RVW_BOOT_FREEZE_RUNTIME:-}" ]]; then
  cp="$("${RVW_PYTHON:-$repo/rvw/.venv/bin/python}" "$here/linux/freeze_runtime.py" --classpath "$cp" --out "$RVW_BOOT_FREEZE_RUNTIME")"
fi
[[ -n "$cp" ]] || { echo "No runtime classpath." >&2; exit 2; }
java_args=(-Xss64m -Xmx3g -XX:+UseParallelGC -Driscvsim.script="$here/run.sh" -cp "$cp" rvwvexii.BootSlices "$@")
if [[ -n "${RVW_BOOT_WAVE:-}" ]]; then
  # The backend reuses its test directory. Save this bounded wave before
  # another process can clean that directory, while still holding the lock.
  status=0
  nice -n "$nice_delta" java "${java_args[@]}" || status=$?
  (( status == 0 )) || exit "$status"
  wave="${RVW_BOOT_WORK:-$(dirname "$4")/boot-native}/VexiiRiscv/test/wave.fst"
  if [[ -s "$wave" && -d "$4" ]]; then
    cp "$wave" "$4/wave.fst"
    rm "$wave"
  else
    echo 'The requested wave was not produced.' >&2
    exit 2
  fi
  exit "$status"
fi
exec nice -n "$nice_delta" java "${java_args[@]}"
