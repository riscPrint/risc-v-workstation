#!/usr/bin/env bash
# Build the PicoRV32 copies of the riscv-tests RV32IM tests with the tohost environment.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tests="${PICORV32_TESTS:-$here/../tests}"
prefix="${RISCV_PREFIX:-riscv64-unknown-elf-}"
mkdir -p "$here/out/isa"
for source in "$tests"/*.S; do
  name="$(basename "$source" .S)"
  "${prefix}gcc" -march=rv32im -mabi=ilp32 -nostdlib -nostartfiles -include "$here/env/riscv_test.h" -I"$tests" \
    -T "$here/programs/link.ld" -Wl,--build-id=none "$source" -o "$here/out/isa/$name"
done
