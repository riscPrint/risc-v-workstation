#!/usr/bin/env bash
# Build rv32ui/rv32um/rv32ua p-environment ELFs outside the reference checkout.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source_dir="$(cd "${RISCV_TESTS_SOURCE:-${RVW_HOME:?Set RVW_HOME}/../ref/riscv-tests}" && pwd)"
prefix="${RISCV_PREFIX:-riscv64-unknown-elf-}"
command -v "${prefix}gcc" >/dev/null || { echo "set RISCV_PREFIX to a RISC-V tool prefix or add the compiler to PATH" >&2; exit 2; }
mkdir -p "$here/out/isa"
cd "$here/out/isa"
targets=()
for group in ui um ua; do
  # RV32 test sources reuse RV64 tests through assembler includes.
  for file in "$source_dir/isa/rv32$group/"*.S; do
    targets+=("rv32$group-p-$(basename "$file" .S)")
  done
done
nice -n 10 make -j2 -f "$source_dir/isa/Makefile" src_dir="$source_dir/isa" \
  XLEN=32 RISCV_PREFIX="$prefix" "${targets[@]}"

mkdir -p "$here/out/programs"
for name in smoke trap branches irqs memcsr; do
  "${prefix}gcc" -march=rv32im_zicsr_zifencei -mabi=ilp32 -nostdlib -nostartfiles \
    -T "$here/programs/link.ld" -Wl,--build-id=none "$here/programs/$name.S" -o "$here/out/programs/$name"
done
