#!/usr/bin/env bash
# Builds the tiny test programs into build/ (RISC-V GCC from PATH by default).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/../.." && pwd)"
export RVW_PYTHON="${RVW_PYTHON:-$root/../rvw/.venv/bin/python}"
if [[ "$RVW_PYTHON" != /* ]] || [ ! -x "$RVW_PYTHON" ]; then
  echo "[build.sh] set RVW_PYTHON to an absolute Python interpreter, or create $root/../rvw/.venv" >&2
  exit 2
fi
if [ "${1:-}" = --riscvsim-supervised ]; then
  shift 2
else
  exec "$RVW_PYTHON" "$root/scripts/supervise.py" "$BASH" "$here/build.sh" "$@"
fi
cd "$here"
gcc="${RISCV_GCC:-riscv64-unknown-elf-gcc}"
command -v "$gcc" >/dev/null || { echo "set RISCV_GCC to a RISC-V GCC executable or add it to PATH" >&2; exit 2; }
mkdir -p build
for s in *.S; do
  "$gcc" -march=rv64gc -mabi=lp64d -nostdlib -nostartfiles -static -T link.ld -o "build/${s%.S}" "$s"
done
ls build
