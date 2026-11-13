#!/usr/bin/env bash
# Build rv32ui/rv32um/rv32ua p-environment ELFs outside the reference checkout.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source_dir="$(cd "${RISCV_TESTS_SOURCE:-${RVW_HOME:?Set RVW_HOME}/../ref/riscv-tests}" && pwd)"
prefix="${RISCV_PREFIX:-riscv64-unknown-elf-}"
command -v "${prefix}gcc" >/dev/null || { echo "set RISCV_PREFIX to a RISC-V tool prefix or add the compiler to PATH" >&2; exit 2; }
xlen="${1:-32}"
case "$xlen" in 32|64) ;; *) echo "usage: $0 [32|64]" >&2; exit 2 ;; esac
out="$here/out/isa"
if [ "$xlen" = 64 ]; then out="$here/out/isa64"; fi
mkdir -p "$out"
cd "$out"
targets=()
for group in ui um ua; do
  # RV32 test sources reuse RV64 tests through assembler includes.
  for file in "$source_dir/isa/rv${xlen}$group/"*.S; do
    targets+=("rv${xlen}$group-p-$(basename "$file" .S)")
  done
done
nice -n 10 make -j2 -f "$source_dir/isa/Makefile" src_dir="$source_dir/isa" \
  XLEN="$xlen" RISCV_PREFIX="$prefix" "${targets[@]}"

if [ "$xlen" = 64 ]; then exit 0; fi
mkdir -p "$here/out/programs"
for name in smoke trap; do
  "${prefix}gcc" -march=rv32ima_zicsr_zifencei -mabi=ilp32 -nostdlib -nostartfiles \
    -T "$here/programs/link.ld" -Wl,--build-id=none "$here/programs/$name.S" -o "$here/out/programs/$name"
done
