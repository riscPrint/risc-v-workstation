#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
[ "$#" = 1 ] || { echo 'usage: run-dma.sh NEW_OUTPUT_DIRECTORY' >&2; exit 2; }
mkdir "$1"
out="$(cd "$1" && pwd)"
"${RISCV_GCC:-riscv64-unknown-elf-gcc}" -march=rv64ima_zicsr_zifencei -mabi=lp64 \
  -nostdlib -nostartfiles -Wl,--no-relax -T "$here/link.ld" "$here/dma.S" -o "$out/test.elf"
cd "$here/.."
exec "$repo/scripts/with-lock.sh" boom nice -n 10 "$repo/scripts/with-lock.sh" sbt \
  sbt -batch -Dsbt.offline=true -J-Xmx2g -J-XX:ActiveProcessorCount=2 \
  "boom/Test/runMain riscvsim.boom.DmaCampaign $out/test.elf $out/work"
