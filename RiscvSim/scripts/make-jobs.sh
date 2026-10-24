#!/usr/bin/env bash
# Stand-in for `make` (via SPINAL_MAKE_CMD) that replaces Spinal's `-j<all cores>` with
# -j$RISCVSIM_MAKE_JOBS (default 4), so Verilator C++ builds share the machine.
args=()
for a in "$@"; do
  case "$a" in -j*) ;; *) args+=("$a") ;; esac
done
# Command-line make variables override the tool names in verilated.mk.
# An unpinned direct JVM launch cannot earn a conclusive result or native reuse.
if [ -n "${RISCVSIM_PINNED_BIN:-}" ]; then
  args+=("CXX=$RISCVSIM_PINNED_CXX" "LINK=$RISCVSIM_PINNED_LINK" "AR=$RISCVSIM_PINNED_AR")
fi
exec "${RISCVSIM_PINNED_MAKE:-${RISCVSIM_MAKE:-make}}" -j"${RISCVSIM_MAKE_JOBS:-4}" "${args[@]}"
