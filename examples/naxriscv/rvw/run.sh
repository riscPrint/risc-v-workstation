#!/usr/bin/env bash
# C1 launcher. Reuse the generic supervisor, source identity and native tool capture.
# NaxRiscv and the workstation libraries are compiled with Scala 2.12.18 against NaxRiscv's pinned
# SpinalHDL source (the source axis of scripts/sbt/SpinalAxis.scala).
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
if [ "${1:-}" = --nax-locked ]; then
  shift
else
  exec "$repo/scripts/with-lock.sh" "${RVW_NAX_LOCK:-nax}" "$BASH" "$here/run.sh" \
    --riscvsim-supervised "$launch_owner" --nax-locked "$@"
fi
trap 'exit 143' TERM
trap 'exit 130' INT
trap 'exit 129' HUP
export NAXRISCV="$(cd "${NAXRISCV:-$here/..}" && pwd)"
export RVW_SPINAL_SOURCE="$NAXRISCV/ext/SpinalHDL"
if [ ! -f "$RVW_SPINAL_SOURCE/build.sbt" ]; then
  echo "NaxRiscv submodule ext/SpinalHDL is missing: git -C $NAXRISCV submodule update --init ext/SpinalHDL ext/rvls" >&2
  exit 2
fi
if [ -n "${RISCVSIM_EXTRA_INPUTS:-}" ]; then
  echo 'input_not_captured:custom_build_layout' >&2
  exit 2
fi
export SPINAL_MAKE_CMD="$sim/scripts/make-jobs.sh"
# The pinned SpinalHDL sim wrapper constructs the model before it sets its handle, and Verilator 5
# reads sc_time_stamp() during construction (a null dereference; fixed in later SpinalHDL).
# VL_TIME_CONTEXT makes Verilator use its context time instead. Wave and C1 times come from SpinalSim.
# Verilator 5.052 calls each wide data word EData. The pinned wrapper still uses WData.
export SPINAL_VERILATOR_FLAGS="${SPINAL_VERILATOR_FLAGS:-} -CFLAGS -DWData=EData -CFLAGS -DVL_TIME_CONTEXT"
native_identity="$("$RVW_PYTHON" "$sim/scripts/native-identity.py")"
if [ "${1:-}" = identity ] && [[ "$native_identity" = *'"cache_enabled":false'* ]]; then
  echo 'Native inputs unavailable; refusing identity for result reuse.' >&2
  exit 2
fi
"$RVW_PYTHON" "$sim/scripts/source-identity.py" "$NAXRISCV" "$repo" > "$launch_owner/source.json"
cache="${RISCVSIM_CP_CACHE:-${RISCVSIM_WORK:-$here/target}/nax-classpath.json}"
cache_args=(--root "$repo" --root "$NAXRISCV")
if ! cp="$("$RVW_PYTHON" "$here/classpath-cache.py" load --cache "$cache" "${cache_args[@]}")"; then
  before="$("$RVW_PYTHON" "$here/classpath-cache.py" sources "${cache_args[@]}")"
  output="$(cd "$here" && "$repo/scripts/with-lock.sh" "${RVW_NAX_SBT_LOCK:-sbt-nax}" nice -n 10 \
    sbt -J-Xmx4g -batch -Dsbt.offline=true '++2.12.18!' 'root/compile' 'export root/Runtime/fullClasspath' 2>&1)" || {
    echo "$output" >&2; exit 2;
  }
  cp="$(printf '%s\n' "$output" | grep -v '^\[' | grep 'scala-library' | tail -1)"
  if [ -z "$cp" ]; then echo "$output" >&2; echo 'No classpath in sbt output.' >&2; exit 2; fi
  "$RVW_PYTHON" "$here/classpath-cache.py" save --cache "$cache" --before "$before" --classpath "$cp" "${cache_args[@]}" || true
fi
exec "$RVW_PYTHON" "$sim/scripts/native-identity.py" launch "$native_identity" "$launch_owner" \
  -Xss64m -Xmx"${RISCVSIM_XMX:-4g}" -XX:+UseParallelGC \
  -Driscvsim.cwd="$PWD" -Driscvsim.script="$here/run.sh" \
  -Driscvsim.tools="$repo" -Driscvsim.source="$launch_owner/source.json" \
  -cp "$cp" rvwnax.Main "$@"
