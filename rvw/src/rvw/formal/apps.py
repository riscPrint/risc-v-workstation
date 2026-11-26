"""Shared formal flow and identifier helpers."""
from argparse import Namespace
import contextlib
import io
import json
from pathlib import Path
import re

IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')


def ident(value):
    if not isinstance(value, str) or not IDENT.fullmatch(value) or value.startswith('rvwa_'):
        raise ValueError(f'expected plain identifier: {value}')
    return value


def flow(files, top, clock, reset, out, depth, engine, timeout, mode='bmc', expected_interfaces=None, event_model=False, async_reset=False):
    from .cli import _flow
    args = Namespace(verilog=[str(p) for p in files], top=top, clock=clock, reset=reset,
                     out=str(out), depth=depth, engine=engine, timeout=timeout, mode=mode,
                     expected_interfaces=expected_interfaces or {}, checks=None, reset_active='high', reset_cycles=1, free_reset=False,
                     first_failure=True, tie=None, cut=None, event_model=event_model, event_clock=None,
                     async_reset=async_reset, frontend='verilog', json=False)
    with contextlib.redirect_stdout(io.StringIO()):
        _flow('bmc', args)
    return json.loads((Path(out) / 'result.json').read_text())
