#!/usr/bin/env bash
# Capture the matched Spike ABI inputs, then compile only their private copies.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$here/../rvw/src${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m rvw.cosim.build --source "$here/spike_shim.cc" "${1:-$here/build/librvw_spike.so}"
