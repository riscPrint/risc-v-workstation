#!/usr/bin/env bash
set -euo pipefail
: "${RISCV_TESTS_SOURCE:?Set RISCV_TESTS_SOURCE}"
: "${RVW_FPU_RUN_ROOT:?Set RVW_FPU_RUN_ROOT outside the repository}"
width="${1:?Use 32 or 64}"
case "$width" in 32) groups=(uf uc);; 64) groups=(uf ud uc);; *) exit 2;; esac
source_dir="$(cd "$RISCV_TESTS_SOURCE" && pwd)"
mkdir -p "$RVW_FPU_RUN_ROOT/isa$width"
cd "$RVW_FPU_RUN_ROOT/isa$width"
targets=()
for group in "${groups[@]}"; do
  for file in "$source_dir/isa/rv$width$group/"*.S; do
    targets+=("rv$width$group-p-$(basename "$file" .S)")
  done
done
nice -n 15 make -j2 -f "$source_dir/isa/Makefile" src_dir="$source_dir/isa" \
  XLEN="$width" RISCV_PREFIX="${RISCV_PREFIX:-riscv64-unknown-elf-}" "${targets[@]}"
