#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$here/../../programs"
for name in hello interrupt external; do
  "${RISCV_GCC:-riscv64-unknown-elf-gcc}" -march=rv32i_zicsr -mabi=ilp32 -nostdlib -nostartfiles -Wl,-T,"$here/link.ld" -o "$here/../../programs/$name" "$here/$name.S"
done
