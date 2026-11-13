#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
exec nice -n 15 "${RVW_HOME:?}/rvw/.venv/bin/python" "$here/adapter.py" "$@"
