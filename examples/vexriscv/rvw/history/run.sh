#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${RVW_HOME:?}/scripts/with-lock.sh" "${RVW_VEX_LOCK:-vex-history}" nice -n 10 \
  "${RVW_PYTHON:?}" "$here/driver.py" "$@"
