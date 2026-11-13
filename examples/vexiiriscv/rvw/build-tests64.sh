#!/usr/bin/env bash
# Build RV64 UI/UM/UA without writing to the reference checkout.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source_dir="$(cd "${RISCV_TESTS_SOURCE:-${RVW_HOME:?Set RVW_HOME}/../ref/riscv-tests}" && pwd)"
prefix="${RISCV_PREFIX:-riscv64-unknown-elf-}"
command -v "${prefix}gcc" >/dev/null
mkdir -p "$here/out/isa64"
cd "$here/out/isa64"
targets=()
for group in ui um ua; do
  for file in "$source_dir/isa/rv64$group/"*.S; do
    targets+=("rv64$group-p-$(basename "$file" .S)")
  done
done
nice -n 10 make -j2 -f "$source_dir/isa/Makefile" src_dir="$source_dir/isa" \
  XLEN=64 RISCV_PREFIX="$prefix" "${targets[@]}"
