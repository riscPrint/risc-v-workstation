#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/../../.." && pwd)"
out="$1"
mkdir "$out"
out="$(cd "$out" && pwd)"
python="${RVW_PYTHON:-$root/rvw/.venv/bin/python}"
gcc="${RISCV_PREFIX:-riscv64-unknown-elf-}gcc"
"$python" "$here/csr-program.py" "$here/csr.json" "$out/csr.S"
for program in irq csr; do
  source="$out/csr.S"
  if [[ "$program" == irq ]]; then source="$here/interrupt.S"; fi
  "$gcc" -nostdlib -march=rv32im_zicsr -mabi=ilp32 -Wl,--no-relax \
    "-Wl,-T,$here/program.ld" "$source" -o "$out/$program.elf"
done
