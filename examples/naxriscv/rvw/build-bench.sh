#!/usr/bin/env bash
# Build riscv-tests benchmarks for RV32IM into rvw/out/bench with the workstation's bare-metal
# benchmark build (Arch/bench). RV32IM, not RV32IMA: the GCC multilib has an rv32im libgcc.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "${RVW_HOME:?Set RVW_HOME}" && pwd)"
source_dir="${RISCV_TESTS_SOURCE:-$("${RVW:-rvw}" doctor --resolve riscv-tests --acquire)}"
prefix="${RISCV_PREFIX:-riscv64-unknown-elf-}"
mkdir -p "$here/out/bench"
make -s -C "$repo/Arch/bench" SRC="$source_dir/benchmarks" BARE_CC="${prefix}gcc" MARCH=rv32im ABI=ilp32 \
  BUILD="$here/out/bench" ${BENCH:+BENCHES="$BENCH"}
