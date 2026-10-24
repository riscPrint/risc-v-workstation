#!/usr/bin/env bash
# Spinal 1.15 uses OSHI's host CPU count, ignoring ActiveProcessorCount.
# Appending -j4 overrides its earlier -jN without changing the shared checkout.
set -euo pipefail
exec make "$@" -j4
