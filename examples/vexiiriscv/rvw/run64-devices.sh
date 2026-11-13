#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
: "${RVW_DEVICE_LIBRARY:?Build the DeviceApiV1 library and set RVW_DEVICE_LIBRARY}"
: "${PYTHONHOME:?Set PYTHONHOME to the selected plugin CPython installation}"
: "${PYTHONPATH:?Set PYTHONPATH to the selected workstation rvw/src directory}"
export RVW_VEX_DEVICE_MAP="$here/devices64.json"
exec "$here/run64.sh" "$@"
