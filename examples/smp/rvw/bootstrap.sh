#!/usr/bin/env bash
# Fetch pinned external sources. Run once, outside this repository.
set -euo pipefail
: "${VEXIIRISCV:?Set VEXIIRISCV to a new external directory}"
git clone https://github.com/SpinalHDL/VexiiRiscv "$VEXIIRISCV"
git -C "$VEXIIRISCV" checkout --detach 9f70315deb3390b283995c5b8f1bd38215ecf52b
git -C "$VEXIIRISCV" submodule update --init ext/SpinalHDL ext/rvls
