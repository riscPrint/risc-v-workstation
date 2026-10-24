"""A C1 run directory and its artifacts, validated through `rvw.results`."""
from __future__ import annotations

import os
import json
import stat
from dataclasses import dataclass, field
from pathlib import Path

from ..common.capture import _open_read
from ..results import RunResult
from ..results import load_run as load_result


def tools_root() -> Path:
    """The risc-v-workstation checkout this package lives in (RVW_ROOT overrides)."""
    env = os.environ.get("RVW_ROOT")
    if env:
        return Path(env).resolve()
    # rvw/src/rvw/runs/result.py -> repo root is 4 levels up from rvw/
    return Path(__file__).resolve().parents[4]


@dataclass
class Run:
    dir: Path
    result: RunResult
    capture: object = field(default=None, kw_only=True, repr=False)
    captured_artifacts: dict = field(default_factory=dict, kw_only=True, repr=False)
    data: dict = field(default_factory=dict)   # result.to_dict(): every C1 field, extras included

    def __getattr__(self, k):
        try:
            return self.__dict__["data"][k]
        except KeyError:
            raise AttributeError(k) from None

    def get(self, k, default=None):
        return self.data.get(k, default)

    def artifact(self, name: str) -> Path | None:
        """Absolute path of an artifact ('log', 'rvfi_trace', 'wave', 'konata', ...) if it exists."""
        if self.capture is not None:
            return self.captured_artifacts.get(name)
        rel = (self.data.get("artifacts") or {}).get(name)
        if rel:
            p = (self.dir / rel) if not os.path.isabs(rel) else Path(rel)
            if p.exists():
                return p
        # Fall back to the conventional names
        for cand in {"wave": ["wave.vcd", "wave.fst", "wave.vcd.gz"], "rvfi_trace": ["rvfi.jsonl"],
                     "log": ["run.log"], "konata": ["konata.log", "konata.log.gz"]}.get(name, []):
            p = self.dir / cand
            if p.exists():
                return p
        return None

    @property
    def inconclusive(self) -> str | None:
        """Why this result says nothing reliable about the core, or None: the shared rule
        (`rvw.results.inconclusive_cause`): a harness `error`, a synthesized result, a wall-clock
        timeout, C1 `inconclusive`, an unattributed or pending concurrent failure. Such a run neither
        reproduces nor rules out a failure (reduce, bisect, bundle)."""
        return self.result.why_inconclusive

    @property
    def failed(self) -> bool:
        return self.data.get("status") != "pass"


def open_run(path: str | os.PathLike, *, capture=None) -> Run:
    """Open a C1 run directory (or its result.json) with canonical C1 validation.
    Raises FileNotFoundError or a ValueError (`rvw.results.SchemaError`)."""
    p = Path(path)
    f = p / "result.json" if p.is_dir() else p
    if not f.exists():
        raise FileNotFoundError(f"{f}: no result.json (expected a C1 run directory)")
    captured = capture.file(f) if capture is not None else None
    directory = Path(captured.resolved).parent if captured is not None else f.parent.resolve()
    if captured is None:
        r = load_result(f)
    else:
        with os.fdopen(_open_read(captured.copy), 'r') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError(f'{captured.copy}: not a regular file')
            r = RunResult.from_dict(json.load(stream), path=directory)
    run = Run(directory, r, r.to_dict())
    if capture is not None:
        names = set(run.get('artifacts') or {}) | {'wave', 'rvfi_trace', 'log', 'konata', 'pdg'}
        for name in sorted(names):
            declared = (run.get('artifacts') or {}).get(name)
            item = run.artifact(name) if not declared else run.dir / declared
            if item is not None:
                run.captured_artifacts[name] = capture.file(item).copy
        pdg = (run.get('details') or {}).get('pdg')
        if pdg:
            run.captured_artifacts['details_pdg'] = capture.file(Path(pdg)).copy
        run.capture = capture
    return run
