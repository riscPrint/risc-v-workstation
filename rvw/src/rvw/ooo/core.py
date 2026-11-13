"""A bounded, fixed-latency OoO model. No RTL timing enters prediction."""
from collections import Counter, deque
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from io import StringIO
import json
import re
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
    physical_float_registers: int = 0
    branch_penalty: int = 0
    branch_speculation: bool = False
    branch_prediction: str = "sequential"
    issue_order: str = "out_of_order"
    memory_policy: str = "ordered"
    dependence_entries: int = 1024
    replay_penalty: int = 5
    forwarding_latency: int = 1
    frontend: dict = field(default_factory=dict)
    execution: dict = field(default_factory=dict)
    translation: dict = field(default_factory=dict)
    rename: dict = field(default_factory=dict)
    custom_instructions: list = field(default_factory=list)
    components: dict = field(default_factory=dict)
    memory_rename: dict = field(default_factory=dict)

    def __post_init__(self):
        from rvw.csim.config import validate as validate_components
        if not isinstance(self.components, dict):
            raise ValueError("components must be an object")
        validate_components(self.components)
        if self.components.get("memory", {}).get("l1i") and not self.frontend:
            raise ValueError("component instruction cache requires explicit frontend timing")
        if self.translation and self.components.get("memory", {}).get("tlb"):
            raise ValueError("select own translation or component TLB timing, not both")
        from .memory_rename import validate as validate_memory_rename
        validate_memory_rename(self.memory_rename, self.memory_policy)
        from .custom import validate as validate_custom
        validate_custom(self.custom_instructions, self.latencies)
        from .rename import validate
        validate(self.rename)
        from .frontend import FrontendConfig
        from .execution import Execution
        from .translation import Translation
        if not isinstance(self.frontend, dict):
            raise ValueError("frontend must be an object")
        if self.frontend.get('fdip') and not self.components.get('memory', {}).get('l1i'):
            raise ValueError("fdip requires component memory.l1i")
        if self.frontend:
            FrontendConfig(**self.frontend)
        Execution(self.execution)
        if self.translation:
            Translation(self.translation)
        for key, value in asdict(self).items():
            if key in ("fetch_width", "fetch_entries", "rename_width", "rob_entries",
                       "issue_width", "issue_entries", "load_entries", "store_entries", "commit_width") and (type(value) is not int or value < 1):
                raise ValueError(f"{key} must be a positive integer")
        if not isinstance(self.latencies, dict) or not self.latencies:
            raise ValueError("latencies must be a nonempty object")
        for key, value in self.latencies.items():
            if key not in ("alu", "multiply", "divide", "load", "store", "branch", "jump", "csr", "fence", "system") and not re.fullmatch("(?:custom|fp)_[a-zA-Z0-9_]+", key):
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
        if type(self.physical_float_registers) is not int or (self.physical_float_registers != 0 and self.physical_float_registers < 33):
            raise ValueError("physical_float_registers must be zero (unbounded) or at least 33")
        if self.issue_order not in ("in_order", "out_of_order"):
            raise ValueError("issue_order must be in_order or out_of_order")
        if self.branch_prediction not in ("sequential", "static_btfn"):
            raise ValueError("unsupported branch_prediction")
        if self.branch_prediction != "sequential" and any(k in self.components for k in ("branch", "btb", "ras", "indirect")):
            raise ValueError("select static prediction or component prediction")
        if type(self.branch_speculation) is not bool:
            raise ValueError("branch_speculation must be boolean")
        if type(self.branch_penalty) is not int or self.branch_penalty < 0:
            raise ValueError("branch_penalty must be nonnegative")
        if self.memory_policy not in ("ordered", "disambiguate", "speculate"):
            raise ValueError("unsupported memory_policy")
        for key in ("dependence_entries", "replay_penalty"):
            if type(getattr(self, key)) is not int or getattr(self, key) < 1:
                raise ValueError(f"{key} must be positive")
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
    encoding: int = 0
    mnemonic: str = ""


@dataclass(eq=False)
class Entry:
    insn: Instruction
    deps: tuple
    done: int | None = None
    bypass_ready: int = 0
    register: bool = True
    translation_ready: int | None = None
    predicted_correct: bool | None = None
    data_producer: object = None


def simulate(instructions, config, max_cycles=1_000_000, predictor=None, memory=None, backend="auto", observer=None):
    if not config.components:
        return _simulate(instructions, config, max_cycles, predictor, memory, backend, observer=observer)
    instructions = list(instructions)
    if backend != "python" and observer is None and predictor is None and memory is None:
        # Keep the public input checks in _simulate before entering native code.
        result = _simulate(instructions, config, max_cycles, backend=backend)
        if result.get("backend") == "native":
            return result
    if predictor is not None or memory is not None or backend == "native":
        raise ValueError("component configuration requires its own Python timing adapters")
    from .components import Adapter
    with Adapter(config.components) as adapter:
        branch = any(key in config.components for key in ("branch", "btb", "ras", "indirect"))
        result = _simulate(instructions, config, max_cycles,
                           predictor=adapter if branch else None,
                           memory=adapter if "memory" in config.components else None,
                           backend="python", observer=observer, instruction_memory=adapter if config.components.get("memory", {}).get("l1i") else None)
        result["events"].update(adapter.events)
        result["components"] = adapter.stats(result["instret"])
        from .component_events import counters
        result["events"].update(counters(result["components"]))
        return result


def _simulate(instructions, config, max_cycles=1_000_000, predictor=None, memory=None, backend="auto", instruction_memory=None, observer=None):
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
        if any(type(r) is not int or not 0 <= r < 64 or (r >= 32 and not (op.kind.startswith("fp_") or op.kind == "store")) for r in op.sources):
            raise ValueError("invalid source register")
        if (config.memory_policy in ("disambiguate", "speculate") or config.translation or config.memory_rename or memory is not None or config.components.get("memory")) and op.kind in ("load", "store"):
            if type(op.address) is not int or op.address < 0 or type(op.size) is not int or op.size < 1:
                raise ValueError("disambiguate requires memory address and size")
        if op.mnemonic == "fence.i" and (config.components.get("memory", {}).get("l1i") or config.frontend.get("uop_cache_entries", 0)):
            raise ValueError("fence.i requires instruction-cache invalidation not exposed by the component interface")
        if op.kind == "csr" and op.encoding >> 20 == 0x180 and ((op.encoding >> 12 & 7) in (1, 5) or (op.encoding >> 15 & 31)) and config.components.get("memory", {}).get("tlb"):
            raise ValueError("satp changes require translation context handling not exposed by the component interface")
        if op.dest is not None and (type(op.dest) is not int or not 0 <= op.dest < 64 or (op.dest >= 32 and not (op.kind.startswith("fp_") or op.kind == "load"))):
            raise ValueError("invalid destination register")
    if backend not in ("auto", "python", "native"):
        raise ValueError("backend must be auto, python or native")
    if observer is not None:
        if backend == "native":
            raise ValueError("region attribution requires Python timing")
        backend = "python"
    if backend != "python" and predictor is None and memory is None:
        from .native import simulate as native_simulate
        result = native_simulate(instructions, config, max_cycles)
        if result is not None:
            return dict(result, backend="native")
        if backend == "native":
            raise ValueError("native scheduler unavailable for this configuration")
        if config.components:
            return {}
    from .frontend import Frontend
    from .execution import Execution
    from .translation import Translation
    from .attribution import Attribution
    frontend = Frontend(config.frontend, config.fetch_width, config.fetch_entries) if config.frontend else None
    execution = Execution(config.execution)
    translation = Translation(config.translation) if config.translation else None
    attribution = Attribution(config.commit_width)
    rob, fetched, waiting = deque(), deque(), []
    writers, events, peaks = {}, Counter(), Counter()
    pc = retired = loads = stores = allocated = allocated_float = 0
    blocked_until = 0
    unresolved_branch = None
    # Predictors implement predict(pc, fallthrough) and update(pc, actual_next).
    from .structures import StaticPredictor, BackwardPredictor
    predictor = predictor or (BackwardPredictor() if config.branch_prediction == "static_btfn" else StaticPredictor())

    from .control import SERIAL
    from .rename import elimination, fuses
    from .memory_rename import source as memory_source
    from .dependence import Dependence
    dependence = Dependence(config.dependence_entries)
    for cycle in range(max_cycles):
        for entry in rob:
            if entry.bypass_ready and entry.done is None and all(dep.done is not None for dep in entry.deps):
                entry.done = max([entry.bypass_ready] + [dep.done for dep in entry.deps])
        committed = 0
        committed_entries = [] if observer is not None else None
        for _ in range(config.commit_width):
            if not rob or rob[0].done is None or rob[0].done > cycle:
                break
            entry = rob.popleft()
            if observer is not None:
                committed_entries.append(entry)
            retired += 1
            committed += 1
            if entry.register and entry.insn.dest:
                if entry.insn.dest < 32:
                    allocated -= 1
                else:
                    allocated_float -= 1
            loads -= entry.insn.kind == "load"
            stores -= entry.insn.kind == "store"
        attribution.observe(committed, cycle < blocked_until, bool(rob))
        if observer is not None:
            observer.cycle = cycle
            observer.observe(committed_entries, rob, cycle < blocked_until,
                             instructions[retired].pc if retired < len(instructions) else None)
        if retired == len(instructions):
            if frontend:
                events.update(frontend.events)
            events.update(execution.events)
            if translation:
                events.update(translation.events)
            cycles = cycle + 1
            return dict(backend="python", cycles=cycles, instret=retired, ipc=retired / cycles,
                        events=dict(events), max_occupancy=dict(peaks),
                        topdown=attribution.report())
        if unresolved_branch is not None and unresolved_branch.done <= cycle:
            unresolved_branch = None
        issued, dependency_blocked = 0, False
        used_ports = Counter()
        for entry in list(waiting):
            if config.issue_order == "in_order" and entry is not waiting[0]:
                break
            if issued >= config.issue_width:
                break
            if any(dep.done is None or dep.done > cycle for dep in entry.deps):
                dependency_blocked = True
                continue
            older_branches = []
            for previous in rob:
                if previous is entry:
                    break
                if previous.insn.kind in ("branch", "jump") or previous.insn.kind in SERIAL:
                    older_branches.append(previous)
            if cycle < blocked_until or any((p.done is None or p.done > cycle) and not (config.branch_speculation and p.insn.kind in ("branch", "jump") and p.predicted_correct is True) for p in older_branches):
                continue
            speculating = config.branch_speculation and any(p.insn.kind in ("branch", "jump") and p.predicted_correct is True and p.done is not None and p.done > cycle for p in older_branches)
            kind = entry.insn.kind
            if kind in SERIAL:
                older = list(rob)[:list(rob).index(entry)]
                if any(p.done is None or p.done > cycle for p in older):
                    events["control_serialize_blocked"] += 1
                    continue
            if used_ports[kind] >= config.ports.get(kind, config.issue_width):
                events["port_blocked"] += 1
                continue
            if not execution.reserve(kind, cycle, commit=False):
                continue
            latency = config.latencies[kind]
            forwarded = False
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
                    unknown = [p for p in stores_before if p.done is None]
                    if unknown and (config.memory_policy != "speculate" or
                                    any(dependence.waits(entry.insn, p.insn) for p in unknown)):
                        events["store_address_blocked"] += 1
                        continue
                    overlapping = [p for p in stores_before if p.done is not None and
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
                            forwarded = True
                elif any(p.done is None or p.done > cycle for p in older):
                    continue
            if kind in ("load", "store") and translation:
                if entry.translation_ready is None:
                    delay = translation.access(entry.insn.address, entry.insn.size, cycle)
                    if delay is None:
                        continue
                    entry.translation_ready = cycle + delay
                if entry.translation_ready > cycle:
                    continue
            if not execution.reserve(kind, cycle):
                continue
            if forwarded:
                events["forwarded_loads"] += 1
            if kind in ("load", "store") and memory is not None and not forwarded:
                # The component owner supplies access(address, size, write, cycle).
                # It returns an additional service delay in model cycles.
                service = (memory.access_instruction(entry.insn, cycle) if hasattr(memory, "access_instruction") else
                           memory.access(entry.insn.address, entry.insn.size, kind == "store", cycle))
                if type(service) is not int or service < 0:
                    raise ValueError("memory service must return nonnegative cycles")
                latency += service
            if kind in ("branch", "jump", "system"):
                if hasattr(predictor, "predict_instruction"):
                    predicted = predictor.predict_instruction(entry.insn)
                    latency += predictor.last_delay
                    predictor.update_instruction(entry.insn)
                else:
                    predicted = predictor.predict(entry.insn.pc, entry.insn.pc + entry.insn.length)
                    predictor.update(entry.insn.pc, entry.insn.next_pc)
                entry.predicted_correct = predicted == entry.insn.next_pc
                events["branches"] += 1
                if predicted != entry.insn.next_pc:
                    events["branch_misses"] += 1
                    blocked_until = max(blocked_until, cycle + latency + config.branch_penalty)
                    events["wrong_path_fetch_slots_estimate"] += config.branch_penalty * config.fetch_width
                if kind == "system" or not config.branch_speculation or not entry.predicted_correct:
                    unresolved_branch = entry
            if config.memory_policy == "speculate" and kind == "load":
                if any(p.insn.kind == "store" and p.done is None for p in list(rob)[:list(rob).index(entry)]):
                    events["speculative_loads"] += 1
            if config.memory_policy == "speculate" and kind == "store":
                entries = list(rob)
                younger = entries[entries.index(entry)+1:]
                violations = dependence.violations(entry.insn, younger)
                if violations:
                    events["memory_order_replays"] += 1
                    events["memory_order_violations"] += len(violations)
                    events["replayed_instructions"] += len(younger)
                    for victim in younger:
                        victim.done = None
                        victim.translation_ready = None
                        victim.predicted_correct = None
                    younger_set = set(younger)
                    waiting[:] = [item for item in waiting if item not in younger_set]
                    waiting.extend(item for item in younger if not item.bypass_ready)
                    # Keep oldest-ready arbitration after rebuilding the queue.
                    order = {item: index for index, item in enumerate(rob)}
                    waiting.sort(key=order.__getitem__)
                    unresolved_branch = None
                    blocked_until = max(blocked_until, cycle + config.replay_penalty)
            entry.done = cycle + latency
            used_ports[kind] += 1
            waiting.remove(entry)
            issued += 1
            events["issued"] += 1
            if speculating:
                events["correct_path_speculative_issues"] += 1
        events["dependency_blocked"] += dependency_blocked
        for _ in range(config.rename_width):
            if cycle < blocked_until or unresolved_branch is not None:
                break
            if frontend:
                if not frontend.ready(cycle):
                    break
                op = frontend.decoded[0][0]
            else:
                if not fetched:
                    break
                op = fetched[0]
            eliminated = elimination(op, config.rename)
            fused = fuses(rob[-1].insn if rob else None, op, config.rename)
            bypass = eliminated is not None or fused
            alias = memory_source(op, rob) if config.memory_rename else None
            blocked = ("rob_full" if len(rob) >= config.rob_entries else
                       "issue_full" if not bypass and len(waiting) >= config.issue_entries else
                       "distributed_issue_full" if not bypass and execution.queue_full(op.kind, waiting) else
                       "load_full" if op.kind == "load" and loads >= config.load_entries else
                       "store_full" if op.kind == "store" and stores >= config.store_entries else
                       "register_full" if not bypass and alias is None and op.dest and op.dest < 32 and config.physical_registers and allocated >= config.physical_registers - 32 else
                       "float_register_full" if not bypass and op.dest is not None and op.dest >= 32 and config.physical_float_registers and allocated_float >= config.physical_float_registers - 32 else None)
            if blocked:
                events[blocked] += 1
                break
            if frontend:
                frontend.pop()
            else:
                fetched.popleft()
            deps = tuple(writers[r] for r in op.sources if r and r in writers)
            if eliminated == "zero":
                deps = ()
            if fused:
                deps = (rob[-1],)
            entry = Entry(op, deps, bypass_ready=cycle + 1 if bypass else 0, register=not bypass and alias is None)
            if op.kind == "store" and len(op.sources) == 2 and op.sources[1]:
                entry.data_producer = writers.get(op.sources[1])
            if not bypass and alias is None and op.dest:
                if op.dest < 32:
                    allocated += 1
                else:
                    allocated_float += 1
            if op.dest:
                if alias is not None:
                    if alias.data_producer is not None:
                        writers[op.dest] = alias.data_producer
                    else:
                        writers.pop(op.dest, None)
                    events["memory_renamed_loads"] += 1
                else:
                    writers[op.dest] = entry
            rob.append(entry)
            if bypass:
                events["fused_immediates" if fused else eliminated + "_eliminated"] += 1
            else:
                waiting.append(entry)
            loads += op.kind == "load"
            stores += op.kind == "store"
        if frontend:
            frontend.advance(cycle, instructions, cycle < blocked_until or unresolved_branch is not None, memory=instruction_memory)
        for _ in range(0 if frontend else config.fetch_width):
            if cycle < blocked_until or unresolved_branch is not None:
                break
            if pc == len(instructions) or len(fetched) == config.fetch_entries:
                break
            fetched.append(instructions[pc])
            pc += 1
        for name, count in dict(rob_entries=len(rob), issue_entries=len(waiting),
                                load_entries=loads, store_entries=stores,
                                fetch_entries=len(frontend.fetch) if frontend else len(fetched),
                                decode_entries=len(frontend.decoded) if frontend else 0).items():
            peaks[name] = max(peaks[name], count)
    raise ValueError("model cycle budget exhausted")


def _instruction(row, xlen, custom_instructions=()):
    """Decode one validated non-trapping C2 row for a selected timing window."""
    from .custom import decode as decode_custom
    custom = decode_custom(row, custom_instructions)
    if custom is not None:
        kind, sources, dest = custom
        return Instruction(kind, sources, dest, row['pc'], row['pc_next'], 4,
                           encoding=row['insn'], mnemonic=kind)
    decoded = decode(row['insn'], xlen)
    from .control import supported
    if not supported(decoded):
        raise ValueError(f'unsupported control instruction: {decoded.mnemonic}')
    if decoded.cls not in ('alu', 'multiply', 'divide', 'load', 'store', 'branch', 'jump', 'csr', 'fence', 'system', 'float'):
        raise ValueError(f'unsupported instruction: {decoded.mnemonic}')
    mask = row['mem_rmask'] or row['mem_wmask']
    offset = (mask & -mask).bit_length()-1 if mask else 0
    normalized = mask >> offset
    if normalized and normalized != (1 << normalized.bit_length()) - 1:
        raise ValueError('noncontiguous memory mask is unsupported')
    address, size = row['mem_addr'] + offset, normalized.bit_length()
    if size and address + size > 1 << xlen:
        raise ValueError('memory access crosses XLEN address range')
    from .floating import operands
    kind, sources, destination = operands(decoded, row)
    return Instruction(kind, sources, destination, row['pc'], row['pc_next'], decoded.length,
                       address, size, row['insn'], decoded.mnemonic)


def _instructions(data, custom_instructions=()):
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
            if row.get("event") == "irq" and row["levels"] == 0:
                continue  # Inactive input declaration has no timing effect.
            if "event" in row or any(row[k] for k in ("trap", "intr", "halt", "mem_fault")):
                raise ValueError("traps, interrupts and external events are unsupported")
            ops.append(_instruction(row, trace.header['xlen'], custom_instructions))
        if not ended:
            raise ValueError("missing C2 end marker")
        return ops
    finally:
        trace.close()


def run(config_path, trace_path, max_cycles=1_000_000, effective_config=None):
    start = perf_counter()
    config_bytes, trace_bytes = Path(config_path).read_bytes(), Path(trace_path).read_bytes()
    try:
        from .project import configuration
        description = json.loads(config_bytes)
        config = configuration(description)
        if description.get("schema") == "rvw.arch-core/1" and json.loads(trace_bytes.splitlines()[0])["config"] != description["config"]:
            raise ValueError("project description does not match C2 selected config")
    except TypeError as exc:
        raise ValueError(f"invalid model configuration: {exc}") from exc
    from .structures import check_configuration
    configuration = check_configuration(config, effective_config) if effective_config else None
    if configuration and json.loads(trace_bytes.splitlines()[0])["config"] != configuration["config"]:
        raise ValueError("effective configuration does not match C2 selected config")
    if type(max_cycles) is not int or max_cycles < 1:
        raise ValueError("max_cycles must be a positive integer")
    from .native import parse_c2, simulate as native_simulate
    from concurrent.futures import ThreadPoolExecutor
    # Hash immutable input while ctypes runs the native parser and scheduler.
    # The context also joins hashing when parsing or simulation raises.
    with ThreadPoolExecutor(max_workers=1) as hashing:
        trace_digest = hashing.submit(sha256, trace_bytes)
        packed = parse_c2(trace_bytes, config)
        result = native_simulate(packed, config, max_cycles) if packed is not None else None
        if result is None:
            result = simulate(_instructions(trace_bytes, config.custom_instructions), config, max_cycles)
        else:
            result["backend"] = "native"
        result["trace_reader"] = "native-c2" if packed is not None else "python-c2"
        trace_hash = trace_digest.result().hexdigest()
    # Decoder and C2 parser are part of the model identity.
    import rvw.common.riscv as decoder
    import rvw.cosim.trace as parser
    engine = b"".join(Path(p).read_bytes() for p in (__file__, str(Path(__file__).with_name("structures.py")), decoder.__file__, parser.__file__))
    engine += b"".join(Path(__file__).with_name(name + ".py").read_bytes() for name in ("frontend", "execution", "translation", "attribution", "native", "rename", "dependence", "custom", "project", "components", "control", "floating", "component_events", "regions", "memory_rename", "windows"))
    engine += Path(__file__).with_name("native.c").read_bytes()
    engine += Path(__file__).with_name("native_c2.c").read_bytes()
    if result["backend"] == "native":
        from .native import library_path
        engine += library_path().read_bytes()
    if config.components:
        from rvw.csim.engine import source_hash
        engine += source_hash().encode()
    return dict(schema="rvw.ooo-run/1", **result, config=asdict(config),
                config_sha256=sha256(config_bytes).hexdigest(),
                trace_sha256=trace_hash,
                engine_sha256=sha256(engine).hexdigest(), wall_s=perf_counter()-start,
                accuracy_status="inconclusive", configuration_status="snapshot_checked" if configuration else "unchecked",
                configuration_evidence=configuration,
                limits=["fixed latency", "committed path only; no wrong-path resource use",
                        "branch prediction at issue; no speculative predictor history",
                        "cache timing needs a component service; no replay or translation faults",
                        "topdown is an approximate commit-slot partition",
                        "disambiguation uses traced addresses after store issue"],
                cycle_order=["commit", "issue", "rename", *(["decode"] if config.frontend else []), "fetch"])
