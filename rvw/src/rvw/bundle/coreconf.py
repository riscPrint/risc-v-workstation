"""Per-core debug description (TOML), e.g. `RiscvSim/boom/debug.toml`.

The generic bundle code knows no signal names; everything core-specific comes from this file:
the clock and cycle/time mapping, the pipeline-state snapshot (signal groups, counts, tables),
handshake channels to watch, assertion-file -> unit and instruction-class -> unit maps, and how to
run SpinalTrace. See `rvw/src/rvw/bundle/README.md` for the format.

Lookup order: `--core-config PATH`, `$RVW_CORE_CONFIG`, `<tools root>/RiscvSim/<core>/debug.toml`.
"""
from __future__ import annotations

import tomllib
from pathlib import Path


def load(path: str | Path, *, capture=None) -> tuple[dict, Path]:
    p = Path(path)
    saved = capture.file(p).copy if capture is not None else p
    with open(saved, "rb") as f:
        return tomllib.load(f), p
