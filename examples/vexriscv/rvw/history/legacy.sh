#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export RVW_HISTORY_ERA=legacy
exec "$BASH" "$here/run.sh" "$@"
