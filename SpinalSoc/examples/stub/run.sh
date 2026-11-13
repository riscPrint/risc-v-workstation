#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/../../.." && pwd)"
exec "$root/scripts/with-lock.sh" soc-stub "$root/rvw/.venv/bin/python" "$here/adapter.py" "$@"
