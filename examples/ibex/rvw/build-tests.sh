#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
: "${RISCV_TESTS:?Set RISCV_TESTS to a pinned riscv-tests checkout}"
: "${IBEX_WORK:?}"
mkdir -p "$IBEX_WORK/isa"
for suite in rv32ui rv32um rv32uc; do
  for src in "$RISCV_TESTS/isa/$suite"/*.S; do
    name="$suite-p-$(basename "$src" .S)"
    nice -n 15 riscv64-unknown-elf-gcc -march=rv32imc_zicsr_zifencei -mabi=ilp32 \
      -nostdlib -nostartfiles -I"$here" -I"$RISCV_TESTS/isa/macros/scalar" \
      -T "$here/link.ld" -Wl,--build-id=none "$here/boot.S" "$src" -o "$IBEX_WORK/isa/$name"
  done
done
