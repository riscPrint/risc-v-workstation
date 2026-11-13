#!/usr/bin/env bash
# Build the smoke ELF at the mapped RAM and reset PC.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
prefix="${RISCV_PREFIX:-riscv64-unknown-elf-}"
mkdir -p "$here/out/programs"
"${prefix}gcc" -march=rv32im -mabi=ilp32 -nostdlib -nostartfiles -T "$here/programs/link.ld" \
  -Wl,--build-id=none "$here/programs/smoke.S" -o "$here/out/programs/smoke"
