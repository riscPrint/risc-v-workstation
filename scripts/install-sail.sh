#!/usr/bin/env bash
# Separate opt-in Sail setup. Main install.sh does not install Sail.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
case "$(uname -s)-$(uname -m)" in
  Linux-x86_64) asset=Linux-x86_64; checksum=8bb3626a6ce5d45c1d1fa7b907f9d9602cc23270883e470db5d6401f26a2e143 ;;
  Linux-aarch64) asset=Linux-aarch64; checksum=52980f9afb50f2468c61589522d28ac97d74db36ad3fdcdb63b335f5c4286202 ;;
  Darwin-arm64) asset=Mac-arm64; checksum=be025dbf8226de49b89719b14b7a59aa15baef01ce41ddcd50f5fd85c2204ebc ;;
  *) echo 'No pinned Sail 0.15 archive for this host.' >&2; exit 2 ;;
esac
archive="$root/.tools/downloads/sail-0.15-$asset.tar.gz"
mkdir -p "$(dirname "$archive")" "$root/.tools/sail-0.15"
curl -fL --retry 3 "https://github.com/riscv/sail-riscv/releases/download/0.15/sail-riscv-$asset.tar.gz" -o "$archive"
"${RVW_PYTHON:-python3}" -I -c 'import hashlib,pathlib,sys; sys.exit(0 if hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest() == sys.argv[2] else "Sail checksum mismatch")' "$archive" "$checksum"
tar -xzf "$archive" -C "$root/.tools/sail-0.15"
printf 'Set RVW_SAIL to the sail_riscv_sim executable under %s\n' "$root/.tools/sail-0.15"
