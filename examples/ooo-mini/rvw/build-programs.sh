#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p rvw/out/programs rvw/out/isa
nice -n 10 "${RISCV_GCC:-riscv64-unknown-elf-gcc}" -march=rv32im -mabi=ilp32 -nostdlib \
  -T rvw/link.ld rvw/smoke.S -o rvw/out/programs/smoke
for name in fence-selfmod illegal flush-chain; do
  nice -n 10 "${RISCV_GCC:-riscv64-unknown-elf-gcc}" -march=rv32im_zicsr_zifencei -mabi=ilp32 -nostdlib \
    -T rvw/link.ld "rvw/$name.S" -o "rvw/out/programs/$name"
done
if [ "$#" = 1 ]; then
  for program in "$1"/rv32ui-p-* "$1"/rv32um-p-*; do
    [[ "$program" = *.dump ]] && continue
    [ -f "$program" ] && cp "$program" rvw/out/isa/
  done
fi
