#!/usr/bin/env bash
# Export captured debug metadata or launch a native consumer. Never elaborate.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python="${RVW_PYTHON:-$root/rvw/.venv/bin/python}"
exec "$python" -m rvw.query.debug "$@"
