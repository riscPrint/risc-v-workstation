#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
shared="${1:?Pass the directory with the six shared benchmark ELFs}"
out="${2:?Pass a new output directory}"
mkdir -p "$out"
for name in median qsort multiply towers vvadd memcpy; do
  cp "$shared/$name.riscv" "$out/$name.riscv"
done
for name in rob-pressure iq-pressure sq-pressure; do
  df -h /System/Volumes/Data
  available="$(df -Pk /System/Volumes/Data | awk 'NR == 2 {print $4}')"
  if (( available < 15 * 1024 * 1024 )); then
    echo 'native work stopped: less than 15 GiB free' >&2
    exit 2
  fi
  nice -n 10 "${RISCV_GCC:-riscv64-unknown-elf-gcc}" -march=rv32im -mabi=ilp32 -nostdlib \
    -T "$root/rvw/link.ld" "$root/rvw/bench/$name.S" -o "$out/$name.riscv"
done
