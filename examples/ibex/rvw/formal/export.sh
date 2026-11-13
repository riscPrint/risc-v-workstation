#!/usr/bin/env bash
set -euo pipefail
exec nice -n 15 "${RVW_HOME:?}/rvw/.venv/bin/python" "$(dirname "$0")/export.py"
