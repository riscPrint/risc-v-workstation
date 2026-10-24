#!/usr/bin/env bash
# Run a command while holding a named machine-wide lock, so heavy jobs (BOOM Verilator builds,
# sbt compiles of the shared spinal-boom-eda checkout, long BOOM simulations) don't run at once.
#   scripts/with-lock.sh boom sbt -batch ...
# The lock is an OS file lock (flock) held by the command itself: this script execs the helper,
# which execs the command with the lock descriptor open (same pid). Waiters are served in arrival
# order and print who holds the lock. A command that already holds the lock (it inherited the lock
# descriptor and its RVW_LOCKS_HELD entry, e.g. through exec or rvw's run_group) runs at once.
# Implementation and protocol: rvw/src/rvw/common/lock.py.
#   rvw/.venv/bin/python rvw/src/rvw/common/lock.py --status boom
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ $# -lt 2 ]; then echo "usage: $0 NAME CMD [ARGS...]" >&2; exit 2; fi
export RVW_LOCK_PYTHON="${RVW_LOCK_PYTHON:-$here/../rvw/.venv/bin/python}"
if [[ "$RVW_LOCK_PYTHON" != /* ]] || [ ! -x "$RVW_LOCK_PYTHON" ]; then
  echo "[with-lock.sh] set RVW_LOCK_PYTHON to an absolute Python interpreter, or create rvw/.venv" >&2
  exit 2
fi
exec "$RVW_LOCK_PYTHON" -I "$here/../rvw/src/rvw/common/lock.py" "$@"
