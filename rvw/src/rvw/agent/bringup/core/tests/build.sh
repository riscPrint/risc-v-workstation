#!/usr/bin/env bash
# Build the test programs into rvw/out/programs.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
prefix="${RISCV_PREFIX:-riscv64-unknown-elf-}"
out="$here/../rvw/out/programs"
mkdir -p "$out"
for name in smoke arith branch mem; do
  "${prefix}gcc" -march=rv32i -mabi=ilp32 -nostdlib -nostartfiles -T "$here/../link.ld" \
    -Wl,--build-id=none,--no-warn-rwx-segments "$here/$name.S" -o "$out/$name"
done
