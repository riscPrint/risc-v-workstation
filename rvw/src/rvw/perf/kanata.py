"""Reader for the public Kanata 0004 format. No core or ISA assumptions."""
from dataclasses import dataclass, field
import gzip
from pathlib import Path


@dataclass
class Span:
    lane: str
    stage: str
    start: int
    end: int | None = None


@dataclass
class Instruction:
    id: str
    sim_id: str
    thread: str
    start: int
    ordinal: int
    labels: dict[str, str] = field(default_factory=dict)
    spans: list[Span] = field(default_factory=list)
    active: dict[str, Span] = field(default_factory=dict)
    end: int | None = None
    flushed: bool = False


@dataclass
class Trace:
    instructions: dict[str, Instruction]
    start: int
    end: int  # last observed cycle, inclusive
    dependencies: int
    warnings: list[str]


def read(path: str | Path) -> Trace:
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    instructions: dict[str, Instruction] = {}
    cycle = 0
    first_cycle = None
    dependencies = 0
    warnings: list[str] = []
    with opener(path, "rt", encoding="utf-8-sig") as stream:
        if stream.readline().rstrip("\r\n") != "Kanata\t0004":
            raise ValueError(f"{path}: expected Kanata 0004 header")
        for number, line in enumerate(stream, 2):
            fields = line.rstrip("\r\n").split("\t")
            cmd = fields[0]
            if not cmd or cmd.startswith("#"):
                continue
            try:
                if cmd in ("C", "C="):
                    target = int(fields[1]) + (cycle if cmd == "C" else 0)
                    if target < cycle or target < 0:
                        raise ValueError("cycle moved backwards")
                    cycle = target
                    if first_cycle is None:
                        first_cycle = cycle
                    continue
                if first_cycle is None:
                    first_cycle = cycle
                if cmd == "I":
                    _, key, sim, thread = fields[:4]
                    if key in instructions:
                        raise ValueError(f"duplicate instruction ID {key}")
                    instructions[key] = Instruction(key, sim, thread, cycle, len(instructions))
                    continue
                if cmd not in {"L", "S", "E", "R", "W"}:
                    if cmd not in warnings:
                        warnings.append(cmd)
                    continue
                ins = instructions[fields[1]]
                if ins.end is not None:
                    raise ValueError(f"event after terminal R for {ins.id}")
                if cmd == "L":
                    typ = fields[2]
                    text = "\t".join(fields[3:])
                    prev = ins.labels.get(typ)
                    # Type 0 (the name) is appended as Konata does. Type 1+ (hover detail) lines are
                    # one item each (`inst=...`, `rob=...`): keep them apart with a newline.
                    ins.labels[typ] = text if prev is None else prev + ("" if typ == "0" else "\n") + text
                elif cmd == "S":
                    lane, stage = fields[2:4]
                    if lane in ins.active:
                        ins.active[lane].end = cycle
                    span = Span(lane, stage, cycle)
                    ins.spans.append(span)
                    ins.active[lane] = span
                elif cmd == "E":
                    lane, stage = fields[2:4]
                    span = ins.active.pop(lane)
                    if span.stage != stage:
                        raise ValueError(f"ending {stage}, active stage is {span.stage}")
                    span.end = cycle
                elif cmd == "R":
                    if fields[3] not in ("0", "1"):
                        raise ValueError("R type must be 0 or 1")
                    ins.end = cycle
                    ins.flushed = fields[3] == "1"
                    for span in ins.active.values():
                        span.end = cycle
                    ins.active.clear()
                elif cmd == "W":
                    if fields[2] not in instructions:
                        raise ValueError(f"unknown dependency producer {fields[2]}")
                    dependencies += 1
            except (ValueError, KeyError, IndexError) as exc:
                raise ValueError(f"{path}:{number}: invalid {cmd} record: {exc}") from exc
    return Trace(instructions, first_cycle or 0, cycle, dependencies,
                 [f"unknown command ignored: {cmd}" for cmd in warnings])
