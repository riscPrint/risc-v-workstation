#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/../../.." && pwd)"
: "${VEXRISCV:?Set VEXRISCV to your private pinned core checkout}"
exec "$root/scripts/with-lock.sh" vex-soc nice -n 10 "$root/rvw/.venv/bin/python" "$here/adapter.py" "$@"
