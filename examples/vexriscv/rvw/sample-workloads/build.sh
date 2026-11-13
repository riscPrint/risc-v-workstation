#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
out="${1:?output directory outside the checkout}"
mkdir -p "$out"
for kernel in sort compression; do
  flags=()
  if [[ "$kernel" == compression ]]; then flags+=(-DCOMPRESSION); fi
  "${RISCV_PREFIX:-riscv64-unknown-elf-}gcc" -march=rv32im_zicsr_zifencei -mabi=ilp32 \
    -O2 -ffreestanding -fno-builtin -msmall-data-limit=0 -nostdlib -nostartfiles \
    -DSIZE="${SIZE:-1024}" -DROUNDS="${ROUNDS:-10}" "${flags[@]}" \
    -T "$here/link.ld" "$here/start.S" "$here/kernels.c" -o "$out/$kernel.elf"
done
