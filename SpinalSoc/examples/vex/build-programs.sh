#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/../../.." && pwd)"
out="$root/SpinalSoc/programs/vex"
mkdir -p "$out"
for name in hello interrupt external uart_irq; do
  source="$here/$name.S"
  if [ ! -f "$source" ]; then source="$here/../stub/$name.S"; fi
  nice -n 10 "${RISCV_PREFIX:-riscv64-unknown-elf-}gcc" -march=rv32im_zicsr \
    -mabi=ilp32 -nostdlib -nostartfiles -T "$here/../stub/link.ld" "$source" -o "$out/$name"
done
# The existing project helper builds RV32UI/UM ELFs in this worktree.
exec "$root/examples/vexriscv/rvw/build-tests.sh"
