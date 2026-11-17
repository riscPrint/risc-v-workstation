#!/usr/bin/env bash
# The workstation resolver uses scripts/native-manifest.json as its pin authority.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$root/rvw/src${PYTHONPATH:+:$PYTHONPATH}"
exec "${RVW_PYTHON:-python3}" -m rvw doctor --resolve sail --acquire "$@"
