#!/usr/bin/env bash
# Stand-in for `make` (via SPINAL_MAKE_CMD) that replaces Spinal's `-j<all cores>` with
# -j$RISCVSIM_MAKE_JOBS (default 4), so Verilator C++ builds share the machine.
set -e
# Spinal's legacy coverage writer collapses hierarchy unless the context opts in.
# Patch only its generated wrapper. This script's bytes enter native identity.
build_dir="$PWD"
expect_dir=0
for a in "$@"; do
  if [ "$expect_dir" = 1 ]; then build_dir="$a"; expect_dir=0; continue; fi
  case "$a" in -C) expect_dir=1 ;; -C?*) build_dir="${a#-C}" ;; esac
done
for wrapper in "$build_dir"/*__spinalWrapper.cpp; do
  [ -f "$wrapper" ] || continue
  metadata="${wrapper%__spinalWrapper.cpp}__verFiles.dat"
  [ -f "$metadata" ] || continue
  # The older compiler has shared counters. Forcing its writer would invent
  # instance observations from shared counts, so keep its normal collapse rule.
  perl -ne 'if (/^C /) {
      while (/(?:^|\s|\")--(no-)?coverage-per-instance(?=\s|\")/g) {$enabled = $1 ? 0 : 1}
    } END {exit !$enabled}' "$metadata" || continue
  perl -0777 -i -pe 'if (!/forcePerInstance\(true\)/) {
    s/VerilatedCov::write\(/Verilated::threadContextp()->coveragep()->forcePerInstance(true);\n      VerilatedCov::write(/g;
  }' "$wrapper"
done
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
