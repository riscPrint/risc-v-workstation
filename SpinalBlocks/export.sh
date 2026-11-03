#!/usr/bin/env bash
# Export a stored diagram. This command never elaborates the design.
set -euo pipefail
if [ "$#" -ne 2 ]; then
  echo 'usage: SpinalBlocks/export.sh DESIGN.db OUT.json[.gz]' >&2
  exit 2
fi
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$root/rvw/.venv/bin/rvw" query export blocks "$2" --db "$1"
