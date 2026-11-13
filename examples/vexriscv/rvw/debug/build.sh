#!/usr/bin/env bash
# Build the debug loop program (the interop fixture: _start, loop, target, counter).
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
prefix="${RISCV_PREFIX:-riscv64-unknown-elf-}"
mkdir -p "$here/../out/programs"
"${prefix}gcc" -march=rv32im_zicsr_zifencei -mabi=ilp32 -nostdlib -nostartfiles \
  -T "$here/../programs/link.ld" -Wl,--build-id=none \
  "${RVW_HOME:?Set RVW_HOME}/rvw/tests/fixtures/debug/interop.S" -o "$here/../out/programs/debug-loop"
