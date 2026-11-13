"""A bounded, fixed-latency OoO model. No RTL timing enters prediction."""
from collections import Counter, deque
from dataclasses import asdict, dataclass, field
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
    ports: dict[str, int] = field(default_factory=dict)
    physical_registers: int = 0
    branch_penalty: int = 0
    memory_policy: str = "ordered"
    forwarding_latency: int = 1

    def __post_init__(self):
        for key, value in asdict(self).items():
            if key in ("fetch_width", "fetch_entries", "rename_width", "rob_entries",
                       "issue_width", "issue_entries", "load_entries", "store_entries", "commit_width") and (type(value) is not int or value < 1):
                raise ValueError(f"{key} must be a positive integer")
        if not isinstance(self.latencies, dict) or not self.latencies:
            raise ValueError("latencies must be a nonempty object")
        for key, value in self.latencies.items():
            if key not in ("alu", "multiply", "divide", "load", "store", "branch", "jump"):
                raise ValueError(f"unsupported latency class: {key}")
            if type(value) is not int or value < 1:
                raise ValueError(f"invalid latency for {key}")

        if not isinstance(self.ports, dict):
            raise ValueError("ports must be an object")
        for key, value in self.ports.items():
            if key not in self.latencies or type(value) is not int or value < 1:
                raise ValueError("ports must map modeled classes to positive counts")
        if type(self.physical_registers) is not int or (self.physical_registers != 0 and self.physical_registers < 33):
            raise ValueError("physical_registers must be zero (unbounded) or at least 33")
        if type(self.branch_penalty) is not int or self.branch_penalty < 0:
            raise ValueError("branch_penalty must be nonnegative")
        if self.memory_policy not in ("ordered", "disambiguate"):
            raise ValueError("unsupported memory_policy")
        if type(self.forwarding_latency) is not int or self.forwarding_latency < 1:
            raise ValueError("forwarding_latency must be positive")


@dataclass(frozen=True)
class Instruction:
    kind: str
    sources: tuple[int, ...] = ()
    dest: int | None = None
    pc: int = 0
    next_pc: int = 0
    length: int = 4
    address: int | None = None
    size: int = 0


@dataclass(eq=False)
class Entry:
    insn: Instruction
    deps: tuple
    done: int | None = None


def simulate(instructions, config, max_cycles=1_000_000, predictor=None):
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
        if config.memory_policy == "disambiguate" and op.kind in ("load", "store"):
            if type(op.address) is not int or op.address < 0 or type(op.size) is not int or op.size < 1:
                raise ValueError("disambiguate requires memory address and size")
        if op.dest is not None and (type(op.dest) is not int or not 0 <= op.dest < 32):
            raise ValueError("invalid destination register")
    rob, fetched, waiting = deque(), deque(), []
    writers, events, peaks = {}, Counter(), Counter()
    pc = retired = loads = stores = allocated = 0
    blocked_until = 0
    unresolved_branch = None
    # Predictors implement predict(pc, fallthrough) and update(pc, actual_next).
    from .structures import StaticPredictor
    predictor = predictor or StaticPredictor()

    for cycle in range(max_cycles):
        for _ in range(config.commit_width):
            if not rob or rob[0].done is None or rob[0].done > cycle:
                break
            entry = rob.popleft()
            retired += 1
            allocated -= bool(entry.insn.dest)
            loads -= entry.insn.kind == "load"
            stores -= entry.insn.kind == "store"
        if retired == len(instructions):
            cycles = cycle + 1
            return dict(cycles=cycles, instret=retired, ipc=retired / cycles,
                        events=dict(events), max_occupancy=dict(peaks))
        if unresolved_branch is not None and unresolved_branch.done <= cycle:
            unresolved_branch = None
        issued, dependency_blocked = 0, False
        used_ports = Counter()
        for entry in list(waiting):
            if issued >= config.issue_width:
                break
            if any(dep.done is None or dep.done > cycle for dep in entry.deps):
                dependency_blocked = True
                continue
            older_branches = []
            for previous in rob:
                if previous is entry:
                    break
                if previous.insn.kind in ("branch", "jump"):
                    older_branches.append(previous)
            if cycle < blocked_until or any(p.done is None or p.done > cycle for p in older_branches):
                continue
            kind = entry.insn.kind
            if used_ports[kind] >= config.ports.get(kind, config.issue_width):
                events["port_blocked"] += 1
                continue
            latency = config.latencies[kind]
            if kind in ("load", "store"):
                older = []
                for previous in rob:
                    if previous is entry:
                        break
                    if previous.insn.kind in ("load", "store"):
                        older.append(previous)
                if config.memory_policy == "ordered":
                    if any(p.done is None or p.done > cycle for p in older):
                        continue
                elif kind == "load":
                    # Addresses are available only when the older store's inputs are ready.
                    stores_before = [p for p in older if p.insn.kind == "store"]
                    if any(p.done is None for p in stores_before):
                        events["store_address_blocked"] += 1
                        continue
                    overlapping = [p for p in stores_before if
                        p.insn.address < entry.insn.address + entry.insn.size and
                        entry.insn.address < p.insn.address + p.insn.size]
                    if overlapping:
                        store = overlapping[-1]
                        if not (store.insn.address <= entry.insn.address and
                                store.insn.address + store.insn.size >= entry.insn.address + entry.insn.size):
                            if any(p.done > cycle for p in overlapping):
                                events["partial_forward_blocked"] += 1
                                continue
                        else:
                            latency = config.forwarding_latency
                            events["forwarded_loads"] += 1
                elif any(p.done is None or p.done > cycle for p in older):
                    continue
            if kind in ("branch", "jump"):
                predicted = predictor.predict(entry.insn.pc, entry.insn.pc + entry.insn.length)
                predictor.update(entry.insn.pc, entry.insn.next_pc)
                events["branches"] += 1
                if predicted != entry.insn.next_pc:
                    events["branch_misses"] += 1
                    blocked_until = max(blocked_until, cycle + latency + config.branch_penalty)
                unresolved_branch = entry
            entry.done = cycle + latency
            used_ports[kind] += 1
            waiting.remove(entry)
            issued += 1
            events["issued"] += 1
        events["dependency_blocked"] += dependency_blocked
        for _ in range(config.rename_width):
            if cycle < blocked_until or unresolved_branch is not None:
                break
            if not fetched:
                break
            op = fetched[0]
            blocked = ("rob_full" if len(rob) >= config.rob_entries else
                       "issue_full" if len(waiting) >= config.issue_entries else
                       "load_full" if op.kind == "load" and loads >= config.load_entries else
                       "store_full" if op.kind == "store" and stores >= config.store_entries else
                       "register_full" if op.dest and config.physical_registers and allocated >= config.physical_registers - 32 else None)
            if blocked:
                events[blocked] += 1
                break
            fetched.popleft()
            deps = tuple(writers[r] for r in op.sources if r and r in writers)
            entry = Entry(op, deps)
            allocated += bool(op.dest)
            if op.dest:
                writers[op.dest] = entry
            rob.append(entry)
            waiting.append(entry)
            loads += op.kind == "load"
            stores += op.kind == "store"
        for _ in range(config.fetch_width):
            if cycle < blocked_until or unresolved_branch is not None:
                break
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
            if decoded.cls not in ("alu", "multiply", "divide", "load", "store", "branch", "jump") or decoded.dest_bank != "x" or any(bank != "x" for bank, _ in decoded.sources):
                raise ValueError(f"unsupported instruction: {decoded.mnemonic}")
            mask = row["mem_rmask"] or row["mem_wmask"]
            if mask and mask != (1 << mask.bit_length()) - 1:
                raise ValueError("noncontiguous memory mask is unsupported")
            ops.append(Instruction(decoded.cls, tuple(r for _, r in decoded.sources), row["rd"],
                                   row["pc"], row["pc_next"], decoded.length,
                                   row["mem_addr"], mask.bit_length()))
        if not ended:
            raise ValueError("missing C2 end marker")
        return ops
    finally:
        trace.close()


def run(config_path, trace_path, max_cycles=1_000_000, effective_config=None):
    start = perf_counter()
    config_bytes, trace_bytes = Path(config_path).read_bytes(), Path(trace_path).read_bytes()
    try:
        config = Config(**json.loads(config_bytes))
    except TypeError as exc:
        raise ValueError(f"invalid model configuration: {exc}") from exc
    from .structures import check_configuration
    configuration = check_configuration(config, effective_config) if effective_config else None
    if configuration and json.loads(trace_bytes.splitlines()[0])["config"] != configuration["config"]:
        raise ValueError("effective configuration does not match C2 selected config")
    result = simulate(_instructions(trace_bytes), config, max_cycles)
    # Decoder and C2 parser are part of the model identity.
    import rvw.common.riscv as decoder
    import rvw.cosim.trace as parser
    engine = b"".join(Path(p).read_bytes() for p in (__file__, str(Path(__file__).with_name("structures.py")), decoder.__file__, parser.__file__))
    return dict(schema="rvw.ooo-run/1", **result, config=asdict(config),
                config_sha256=sha256(config_bytes).hexdigest(),
                trace_sha256=sha256(trace_bytes).hexdigest(),
                engine_sha256=sha256(engine).hexdigest(), wall_s=perf_counter()-start,
                accuracy_status="inconclusive", configuration_status="snapshot_checked" if configuration else "unchecked",
                configuration_evidence=configuration,
                limits=["fixed latency", "committed path only; no wrong-path resource use",
                        "branch prediction at issue; no speculative predictor history",
                        "no cache, TLB, replay or shared functional unit port model",
                        "disambiguation uses traced addresses after store issue"],
                cycle_order=["commit", "issue", "rename", "fetch"])
