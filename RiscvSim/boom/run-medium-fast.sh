#!/usr/bin/env bash
# Opt in to the qualified two-thread BOOM medium configuration.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for arg in "$@"; do
  case "$arg" in
    --config|--config=*) echo '[run-medium-fast.sh] config is fixed to medium' >&2; exit 2 ;;
  esac
done
if [[ "${SPINAL_VERILATOR_FLAGS:-}" == *--threads* ]]; then
  echo '[run-medium-fast.sh] remove inherited --threads before selecting this profile' >&2
  exit 2
fi
export SPINAL_VERILATOR_FLAGS="${SPINAL_VERILATOR_FLAGS:+$SPINAL_VERILATOR_FLAGS }--threads 2"
exec "$here/run.sh" run --config medium "$@"
