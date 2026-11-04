"""A bounded, fixed-latency OoO model. No RTL timing enters prediction."""
from collections import Counter, deque
from dataclasses import asdict, dataclass
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from time import perf_counter

from rvw.common.riscv import decode
from rvw.cosim.trace import Trace


@dataclass(frozen=True)
class Config:
    fetch_width: int
    fetch_entries: int
    rename_width: int
    rob_entries: int
    issue_width: int
    issue_entries: int
    load_entries: int
    store_entries: int
    commit_width: int
    latencies: dict[str, int]

    def __post_init__(self):
        for key, value in asdict(self).items():
            if key != "latencies" and (type(value) is not int or value < 1):
                raise ValueError(f"{key} must be a positive integer")
        if not isinstance(self.latencies, dict) or not self.latencies:
            raise ValueError("latencies must be a nonempty object")
        for key, value in self.latencies.items():
            if key not in ("alu", "multiply", "divide", "load", "store"):
                raise ValueError(f"unsupported latency class: {key}")
            if type(value) is not int or value < 1:
                raise ValueError(f"invalid latency for {key}")


@dataclass(frozen=True)
class Instruction:
    kind: str
    sources: tuple[int, ...] = ()
    dest: int | None = None


@dataclass(eq=False)
class Entry:
    insn: Instruction
    deps: tuple
    done: int | None = None


def simulate(instructions, config, max_cycles=1_000_000):
    """Commit, issue, rename, fetch. Latency 1 completes next cycle.

    Memory instructions issue only after older memory instructions complete.
    Queue slots persist through completion until ordered commit.
    """
    if type(max_cycles) is not int or max_cycles < 1:
        raise ValueError("max_cycles must be a positive integer")
    instructions = list(instructions)
    if not instructions:
        raise ValueError("empty instruction stream")
    for op in instructions:
        if op.kind not in config.latencies:
            raise ValueError(f"unsupported instruction class: {op.kind}")
        if any(type(r) is not int or not 0 <= r < 32 for r in op.sources):
            raise ValueError("invalid source register")
        if op.dest is not None and (type(op.dest) is not int or not 0 <= op.dest < 32):
            raise ValueError("invalid destination register")
    rob, fetched, waiting = deque(), deque(), []
    writers, events, peaks = {}, Counter(), Counter()
    pc = retired = loads = stores = 0
    for cycle in range(max_cycles):
        for _ in range(config.commit_width):
            if not rob or rob[0].done is None or rob[0].done > cycle:
                break
            entry = rob.popleft()
            retired += 1
            loads -= entry.insn.kind == "load"
            stores -= entry.insn.kind == "store"
        if retired == len(instructions):
            cycles = cycle + 1
            return dict(cycles=cycles, instret=retired, ipc=retired / cycles,
                        events=dict(events), max_occupancy=dict(peaks))
        issued, dependency_blocked = 0, False
        for entry in list(waiting):
            if issued >= config.issue_width:
                break
            if any(dep.done is None or dep.done > cycle for dep in entry.deps):
                dependency_blocked = True
                continue
            if entry.insn.kind in ("load", "store"):
                older = []
                for previous in rob:
                    if previous is entry:
                        break
                    if previous.insn.kind in ("load", "store"):
                        older.append(previous)
                if any(p.done is None or p.done > cycle for p in older):
                    continue
            entry.done = cycle + config.latencies[entry.insn.kind]
            waiting.remove(entry)
            issued += 1
            events["issued"] += 1
        events["dependency_blocked"] += dependency_blocked
        for _ in range(config.rename_width):
            if not fetched:
                break
            op = fetched[0]
            blocked = ("rob_full" if len(rob) >= config.rob_entries else
                       "issue_full" if len(waiting) >= config.issue_entries else
                       "load_full" if op.kind == "load" and loads >= config.load_entries else
                       "store_full" if op.kind == "store" and stores >= config.store_entries else None)
            if blocked:
                events[blocked] += 1
                break
            fetched.popleft()
            deps = tuple(writers[r] for r in op.sources if r and r in writers)
            entry = Entry(op, deps)
            if op.dest:
                writers[op.dest] = entry
            rob.append(entry)
            waiting.append(entry)
            loads += op.kind == "load"
            stores += op.kind == "store"
        for _ in range(config.fetch_width):
            if pc == len(instructions) or len(fetched) == config.fetch_entries:
                break
            fetched.append(instructions[pc])
            pc += 1
        for name, count in dict(rob_entries=len(rob), issue_entries=len(waiting),
                                load_entries=loads, store_entries=stores,
                                fetch_entries=len(fetched)).items():
            peaks[name] = max(peaks[name], count)
    raise ValueError("model cycle budget exhausted")


def _instructions(data):
    trace = Trace(StringIO(data.decode()))
    try:
        if trace.multihart:
            raise ValueError("multi-hart timing is unsupported")
        ops, ended = [], False
        for row in trace:
            if row.get("event") == "end":
                if row["status"] != "pass":
                    raise ValueError("trace end is not pass")
                ended = True
                continue
            if "event" in row or any(row[k] for k in ("trap", "intr", "halt", "mem_fault")):
                raise ValueError("traps, interrupts and external events are unsupported")
            decoded = decode(row["insn"], trace.header["xlen"])
            if decoded.cls not in ("alu", "multiply", "divide", "load", "store") or decoded.dest_bank != "x" or any(bank != "x" for bank, _ in decoded.sources):
                raise ValueError(f"unsupported instruction: {decoded.mnemonic}")
            ops.append(Instruction(decoded.cls, tuple(r for _, r in decoded.sources), row["rd"]))
        if not ended:
            raise ValueError("missing C2 end marker")
        return ops
    finally:
        trace.close()


def run(config_path, trace_path, max_cycles=1_000_000):
    start = perf_counter()
    config_bytes, trace_bytes = Path(config_path).read_bytes(), Path(trace_path).read_bytes()
    try:
        config = Config(**json.loads(config_bytes))
    except TypeError as exc:
        raise ValueError(f"invalid model configuration: {exc}") from exc
    result = simulate(_instructions(trace_bytes), config, max_cycles)
    # Decoder and C2 parser are part of the model identity.
    import rvw.common.riscv as decoder
    import rvw.cosim.trace as parser
    engine = b"".join(Path(p).read_bytes() for p in (__file__, decoder.__file__, parser.__file__))
    return dict(schema="rvw.ooo-run/1", **result, config=asdict(config),
                config_sha256=sha256(config_bytes).hexdigest(),
                trace_sha256=sha256(trace_bytes).hexdigest(),
                engine_sha256=sha256(engine).hexdigest(), wall_s=perf_counter()-start,
                accuracy_status="inconclusive", configuration_status="unchecked",
                limits=["fixed latency", "committed path only", "conservative memory order",
                        "no branch, cache, TLB, replay or functional unit port model"],
                cycle_order=["commit", "issue", "rename", "fetch"])
