"""Reader for the compact probe event stream `rvw.probe-events/1` (see PLATFORM_CONTRACTS.md)."""
from __future__ import annotations

import gzip
import json
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA = "rvw.probe-events/1"
KINDS = ("branch", "cache", "bus", "tlb", "walk", "stage", "retire", "flush", "stall", "csr", "interrupt",
         "trace", "counter", "fault", "custom")


@dataclass
class Probe:
    id: int
    kind: str
    name: str
    fields: list[tuple[str, int]]
    meta: dict = field(default_factory=dict)

    @property
    def names(self) -> list[str]:
        return [n for n, _ in self.fields]


@dataclass
class Stream:
    header: dict
    probes: list[Probe]
    rows: list[tuple[int, int, list[int]]]
    end: dict | None

    @property
    def identity(self) -> dict:
        return self.header.get("identity") or {}

    def of_kind(self, kind: str) -> list[Probe]:
        return [p for p in self.probes if p.kind == kind]

    def events(self, *kinds: str):
        """Yield (cycle, probe, {field: value}) in stream order for the given kinds."""
        want = {p.id for p in self.probes if not kinds or p.kind in kinds}
        for cycle, pid, values in self.rows:
            if pid in want:
                p = self.probes[pid]
                yield cycle, p, dict(zip(p.names, values))

    @property
    def counters(self) -> dict[str, int]:
        return {k: int(v) for k, v in ((self.end or {}).get("counters") or {}).items()}


def _open(path: Path):
    return gzip.open(path, "rt") if path.suffix == ".gz" else path.open()


def parse_probe(d: dict) -> Probe:
    if d.get("kind") not in KINDS:
        raise ValueError(f"unknown probe kind {d.get('kind')!r}")
    return Probe(int(d["id"]), d["kind"], str(d["name"]), [(str(n), int(w)) for n, w in d["fields"]],
                 dict(d.get("meta") or {}))


def read(path) -> Stream:
    """Read and check a stream. A missing end record (an interrupted run) gives `end=None`."""
    path = Path(path)
    with _open(path) as f:
        first = f.readline()
        if not first.strip():
            raise ValueError(f"{path}: empty probe stream")
        header = json.loads(first)
        if header.get("schema") != SCHEMA:
            raise ValueError(f"{path}: expected {SCHEMA} header")
        probes = [parse_probe(p) for p in header.get("probes", [])]
        if [p.id for p in probes] != list(range(len(probes))):
            raise ValueError(f"{path}: probe ids must be 0..n-1 in order")
        rows, end, last = [], None, -1
        for n, line in enumerate(f, 2):
            if not line.strip():
                continue
            if end is not None:
                raise ValueError(f"{path}:{n}: data after the end record")
            r = json.loads(line)
            if isinstance(r, dict):
                if not r.get("end"):
                    raise ValueError(f"{path}:{n}: unknown record")
                end = r
                continue
            cycle, pid, values = int(r[0]), int(r[1]), [int(v) for v in r[2:]]
            if cycle < last:
                raise ValueError(f"{path}:{n}: cycles must not decrease")
            last = cycle
            if not 0 <= pid < len(probes) or len(values) != len(probes[pid].fields):
                raise ValueError(f"{path}:{n}: row does not match its probe")
            rows.append((cycle, pid, values))
    return Stream(header, probes, rows, end)
