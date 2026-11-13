#!/usr/bin/env bash
set -euo pipefail
export RVW_VEX_XLEN=64
exec "$(dirname "$0")/run.sh" "$@"
