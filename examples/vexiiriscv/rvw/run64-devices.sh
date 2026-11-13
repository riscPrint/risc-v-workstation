#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
: "${RVW_DEVICE_LIBRARY:?Build the DeviceApiV1 library and set RVW_DEVICE_LIBRARY}"
# The library embeds its Python home and rvw/src (RiscvSim/scripts/build-devices.py).
if [ -n "${PYTHONHOME:-}${PYTHONPATH:-}" ]; then
  echo 'Unset PYTHONHOME and PYTHONPATH: native identity cannot enumerate their inputs.' >&2
  exit 2
fi
export RVW_VEX_DEVICE_MAP="$here/devices64.json"
exec "$here/run64.sh" "$@"
