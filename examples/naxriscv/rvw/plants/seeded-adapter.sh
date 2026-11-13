#!/usr/bin/env bash
set -euo pipefail
exec "${RVW_HOME:?Set RVW_HOME}/examples/naxriscv/rvw/run.sh" "$@" --seed 1 --mem-latency 0
