#!/usr/bin/env python3
"""Own a shell launch from startup through process-group and capture cleanup."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import signal
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'rvw/src'))
from rvw.common.proc import run_group, _defer_cancellation


def cancelled(signum, frame):
    raise SystemExit(128 + signum)


def supervise(bash, script, arguments):
    from rvw.sim.backends import require_native
    try:
        needs = os.environ.get('RISCVSIM_REQUIRES', '')
        require_native('riscvsim-verilator', needs.split(',') if needs else [])
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    owner = None
    try:
        with _defer_cancellation():
            owner = Path(tempfile.mkdtemp(prefix='riscvsim-launch.'))
            (owner / 'pid').write_text(str(os.getpid()))
        # Helpers can own nested groups with a five-second TERM grace period.
        # Keep the shell group alive long enough for those helpers to finish cleanup.
        result = run_group([bash, script, '--riscvsim-supervised', str(owner), *arguments],
                           grace=15)
        return result.returncode if result.returncode >= 0 else 128 - result.returncode
    finally:
        with _defer_cancellation():
            if owner is not None:
                shutil.rmtree(owner)


if __name__ == '__main__':
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, cancelled)
    sys.exit(supervise(sys.argv[1], sys.argv[2], sys.argv[3:]))
