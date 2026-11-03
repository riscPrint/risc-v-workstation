"""Native RISC-V O3 bare-metal model for gem5 v25.1.

Usage: gem5.opt --outdir=OUT Arch/model.py --description PARAMS.json ELF

The description requires schema="rvw.arch-core/1", config, isa and kind="o3".
config is the project's C1 configuration name. isa is descriptive metadata.
The model currently loads RV64 executables. It uses gem5 scalar CPU parameters,
explicit issue queues, LTAGE/loop/BTB parameters, Cache keyword arguments,
and TLB entry counts.
memory_latency is a number of cycles at 1 GHz. RAM is 512 MiB at 0x80000000.
The ELF must export tohost, tohost_exit, setStats and bench_stats. Exactly
two setStats entries mark one ROI. bare.json contains the guest ROI counters.
gem5 shows trends; RTL is the truth.
"""

import argparse
import json
import math
import mmap
import os
from pathlib import Path
import struct


RAM_BASE = 0x80000000
RAM_SIZE = 512 * 1024 * 1024
DEFAULT_MAX_TICKS = 100_000_000_000


def _keys(value, required, where):
    if not isinstance(value, dict) or set(value) != set(required):
        raise ValueError(f"{where} must contain exactly: {', '.join(sorted(required))}")


def _integer(value, where, minimum=1):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{where} must be an integer >= {minimum}")


def _scalars(value, where):
    if not isinstance(value, dict) or not value:
        raise ValueError(f"{where} must be a nonempty object of scalar parameters")
    for key, item in value.items():
        if not isinstance(key, str) or type(item) not in (str, int, float, bool):
            raise ValueError(f"{where}.{key} must be a scalar parameter")
        if type(item) is float and not math.isfinite(item):
            raise ValueError(f"{where}.{key} must be finite")


def validate_description(d):
    _keys(d, ("schema", "config", "isa", "kind", "cpu", "queues", "predictor",
              "icache", "dcache", "itlb_entries", "dtlb_entries", "line_bytes",
              "bus_bytes", "memory_latency"), "description")
    if d["schema"] != "rvw.arch-core/1" or d["kind"] != "o3":
        raise ValueError('description requires schema="rvw.arch-core/1" and kind="o3"')
    for key in ("config", "isa"):
        if not isinstance(d[key], str) or not d[key].strip() or d[key] != d[key].strip():
            raise ValueError(f"description.{key} must be a nonempty string without outer whitespace")
    if not d["isa"].startswith("rv64"):
        raise ValueError("description.isa must describe an RV64 core")
    for name in ("cpu", "icache", "dcache"):
        _scalars(d[name], name)
    # These select execution modes or limits owned by this runner.
    forbidden = {"numThreads", "switched_out", "checker", "max_insts_any_thread",
                 "max_insts_all_threads", "max_insts_any_thread_warmup"}
    if forbidden.intersection(d["cpu"]):
        raise ValueError("cpu must not override execution mode or instruction limits")
    for name in ("itlb_entries", "dtlb_entries", "line_bytes", "bus_bytes"):
        _integer(d[name], name)
    if d["line_bytes"] & (d["line_bytes"] - 1):
        raise ValueError("line_bytes must be a power of two")
    latency = d["memory_latency"]
    if type(latency) not in (int, float) or not math.isfinite(latency) or latency <= 0:
        raise ValueError("memory_latency must be a positive finite number of cycles")
    if not isinstance(d["queues"], list) or not d["queues"]:
        raise ValueError("queues must be a nonempty array")
    for i, q in enumerate(d["queues"]):
        _keys(q, ("entries", "units"), f"queues[{i}]")
        _integer(q["entries"], "queue entries")
        if not isinstance(q["units"], list) or not q["units"]:
            raise ValueError("queue units must be a nonempty array")
        for u in q["units"]:
            _keys(u, ("ops", "count", "latency", "pipelined"), "unit")
            _integer(u["count"], "unit count")
            _integer(u["latency"], "unit latency")
            if type(u["pipelined"]) is not bool:
                raise ValueError("unit pipelined must be a boolean")
            if (not isinstance(u["ops"], list) or not u["ops"]
                    or any(not isinstance(op, str) or not op for op in u["ops"])
                    or len(set(u["ops"])) != len(u["ops"])):
                raise ValueError("unit ops must be a nonempty array of distinct opclass names")
    p = d["predictor"]
    _keys(p, ("tage", "loop", "btb", "ras_entries"), "predictor")
    _keys(p["tage"], ("nHistoryTables", "minHist", "maxHist", "tagTableTagWidths",
                      "logTagTableSizes", "logUResetPeriod"), "predictor.tage")
    _keys(p["loop"], ("logSizeLoopPred", "logLoopTableAssoc"), "predictor.loop")
    _keys(p["btb"], ("numEntries", "associativity"), "predictor.btb")
    _integer(p["ras_entries"], "ras_entries")
    t = p["tage"]
    for key in ("nHistoryTables", "minHist", "maxHist", "logUResetPeriod"):
        _integer(t[key], f"tage.{key}")
    if t["minHist"] > t["maxHist"]:
        raise ValueError("tage.minHist must not exceed maxHist")
    for key in ("tagTableTagWidths", "logTagTableSizes"):
        values = t[key]
        if not isinstance(values, list) or len(values) != t["nHistoryTables"] + 1:
            raise ValueError(f"tage.{key} must have nHistoryTables + 1 entries")
        for value in values:
            _integer(value, f"tage.{key}", 0)
    if t["tagTableTagWidths"][0] != 0:
        raise ValueError("tage.tagTableTagWidths[0] must be zero")
    for key, value in p["loop"].items():
        _integer(value, f"loop.{key}", 0)
    if p["loop"]["logLoopTableAssoc"] > p["loop"]["logSizeLoopPred"]:
        raise ValueError("loop associativity must not exceed its size")
    for key, value in p["btb"].items():
        _integer(value, f"btb.{key}")
    if p["btb"]["numEntries"] % p["btb"]["associativity"]:
        raise ValueError("btb.numEntries must be divisible by associativity")
    return d


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_description(path):
    with open(path) as f:
        return validate_description(json.load(f, object_pairs_hook=_unique_object))


def elf_symbols(path, xlen=64):
    """Read an ELF32/ELF64 image. Simulation still requires RV64."""
    elf = Path(path).read_bytes()

    def unpack(fmt, offset):
        if offset < 0 or offset + struct.calcsize(fmt) > len(elf):
            raise ValueError("truncated ELF")
        return struct.unpack_from(fmt, elf, offset)

    def span(offset, size):
        if offset < 0 or size < 0 or offset + size > len(elf):
            raise ValueError("ELF section or segment is outside the file")
        return elf[offset:offset + size]

    if xlen not in (32, 64):
        raise ValueError("ELF xlen must be 32 or 64")
    elf_class = 1 if xlen == 32 else 2
    if len(elf) < (52 if xlen == 32 else 64) or elf[:7] != b"\x7fELF" + bytes((elf_class, 1, 1)):
        raise ValueError(f"expected a little-endian ELF{xlen} executable")
    kind, machine = unpack("<HH", 16)
    if kind != 2 or machine != 243:
        raise ValueError("expected a RISC-V executable")
    entry, phoff, shoff = unpack("<III" if xlen == 32 else "<QQQ", 24)
    phentsize, phnum, shentsize, shnum = unpack("<HHHH", 42 if xlen == 32 else 54)
    if phentsize != (32 if xlen == 32 else 56) or not phnum or shentsize != (40 if xlen == 32 else 64) or not shnum:
        raise ValueError("ELF needs program headers and a symbol table")
    loaded = []
    for i in range(phnum):
        if xlen == 32:
            typ, off, va, pa, filesz, memsz, flags, _ = unpack("<IIIIIIII", phoff + i * phentsize)
        else:
            typ, flags, off, va, pa, filesz, memsz, _ = unpack("<IIQQQQQQ", phoff + i * phentsize)
        if typ == 1:
            span(off, filesz)
            if filesz > memsz or va != pa or not RAM_BASE <= pa < pa + memsz <= RAM_BASE + RAM_SIZE:
                raise ValueError("ELF load segments must fit in bare-metal RAM")
            loaded.append((pa, pa + memsz))
    # Some bare-metal linker scripts omit ELF segment permission flags.
    # M-mode uses the physical mapping; it does not enforce these flags.
    if not any(lo <= entry < hi for lo, hi in loaded):
        raise ValueError("ELF entry must be in a load segment")
    sections = [unpack("<IIIIIIIIII" if xlen == 32 else "<IIQQQQIIQQ", shoff + i * shentsize) for i in range(shnum)]
    syms = {}
    for _, typ, _, _, off, size, link, _, _, entsize in sections:
        if typ != 2:  # SHT_SYMTAB
            continue
        span(off, size)
        if entsize != (16 if xlen == 32 else 24) or size % entsize or link >= len(sections) or sections[link][1] != 3:
            raise ValueError("invalid ELF symbol table")
        strings = span(sections[link][4], sections[link][5])
        for pos in range(off, off + size, entsize):
            if xlen == 32:
                name, value, sz, _, _, index = unpack("<IIIBBH", pos)
            else:
                name, _, _, index, value, sz = unpack("<IBBHQQ", pos)
            if not index:
                continue  # Undefined symbols are not evidence.
            if name >= len(strings) or (end := strings.find(b"\0", name)) < 0:
                raise ValueError("invalid ELF symbol name")
            label = strings[name:end].decode("utf-8")
            if label in ("tohost", "tohost_exit", "setStats", "bench_stats"):
                if label in syms and syms[label] != (value, sz):
                    raise ValueError(f"ambiguous ELF symbol: {label}")
                syms[label] = (value, sz)
    for name, minimum in (("tohost", 8), ("tohost_exit", 1), ("setStats", 1), ("bench_stats", 16)):
        if name not in syms:
            raise ValueError(f"ELF is missing required symbol: {name}")
        addr, size = syms[name]
        if size < minimum or not any(lo <= addr < addr + size <= hi for lo, hi in loaded):
            raise ValueError(f"invalid ELF symbol range: {name}")
    return syms


def make_system(d, binary, syms):
    from m5 import objects as g
    from m5.params import VectorParamDesc
    from m5.SimObject import SimObject

    def scalar_kwargs(cls, values):
        for key in values:
            if key not in cls._params:
                raise ValueError(f"unknown {cls.__name__} parameter: {key}")
            param = cls._params[key]
            if isinstance(param, VectorParamDesc) or issubclass(param.ptype, SimObject):
                raise ValueError(f"{cls.__name__}.{key} must be a scalar gem5 parameter")
        return values

    system = g.System()
    system.clk_domain = g.SrcClockDomain(clock="1GHz", voltage_domain=g.VoltageDomain())
    system.mem_mode = "timing"
    system.mem_ranges = [g.AddrRange(RAM_BASE, size="512MiB")]
    system.cache_line_size = d["line_bytes"]
    system.cpu = cpu = g.RiscvO3CPU(**scalar_kwargs(g.RiscvO3CPU, d["cpu"]))
    queues = []
    for q in d["queues"]:
        units = []
        for u in q["units"]:
            if any(op not in g.OpClass.vals or op == "No_OpClass" for op in u["ops"]):
                raise ValueError("unit ops contains an unknown or empty gem5 opclass")
            units.append(g.FUDesc(count=u["count"], opList=[
                g.OpDesc(opClass=op, opLat=u["latency"], pipelined=u["pipelined"])
                for op in u["ops"]]))
        queues.append(g.IQUnit(numEntries=q["entries"], fuPool=g.FUPool(FUList=units)))
    cpu.instQueues = queues
    p = d["predictor"]
    cpu.branchPred = g.BranchPredictor(
        conditionalBranchPred=g.LTAGE(tage=g.LTAGE_TAGE(**p["tage"]),
                                     loop_predictor=g.LoopPredictor(**p["loop"])),
        btb=g.SimpleBTB(**p["btb"]), ras=g.ReturnAddrStack(numEntries=p["ras_entries"]),
        indirectBranchPred=g.SimpleIndirectPredictor())
    cpu.mmu.itb.size = d["itlb_entries"]
    cpu.mmu.dtb.size = d["dtlb_entries"]
    cpu.addPrivateSplitL1Caches(
        g.Cache(**scalar_kwargs(g.Cache, d["icache"])),
        g.Cache(**scalar_kwargs(g.Cache, d["dcache"])))
    system.membus = g.SystemXBar(width=d["bus_bytes"], frontend_latency=0,
                                forward_latency=0, response_latency=0, snoop_response_latency=0)
    cpu.createInterruptController()
    cpu.connectAllPorts(system.membus.cpu_side_ports, system.membus.cpu_side_ports,
                        system.membus.mem_side_ports)
    system.system_port = system.membus.cpu_side_ports
    system.mem = g.SimpleMemory(range=system.mem_ranges[0],
                               latency=f'{d["memory_latency"]}ns', latency_var="0ns",
                               bandwidth=f'{d["bus_bytes"]}GiB/s')
    system.mem.port = system.membus.mem_side_ports
    system.workload = g.RiscvBareMetal(bootloader=str(binary))
    system.membus.badaddr_responder = g.BadAddr()
    system.membus.default = system.membus.badaddr_responder.pio
    # macOS limits shared-memory names to 31 characters.
    system.shared_backstore = f"/rvwarch{os.getpid()}"
    system.auto_unlink_shared_backstore = True
    targets = [g.PcCountPair(syms["tohost_exit"][0], 1),
               g.PcCountPair(syms["setStats"][0], 1), g.PcCountPair(syms["setStats"][0], 2),
               g.PcCountPair(syms["setStats"][0], 3)]
    system.pc_tracker = g.PcCountTrackerManager(targets=targets)
    cpu.probeListener = g.PcCountTracker(targets=targets, core=cpu, ptmanager=system.pc_tracker)
    cpu.createThreads()
    return system


def read_guest(shm_name, addr, size):
    offset = addr - RAM_BASE
    if offset < 0 or offset + size > RAM_SIZE:
        raise ValueError("guest read is outside RAM")
    try:
        import _posixshmem
    except ImportError:
        fd = os.open("/dev/shm" + shm_name, os.O_RDONLY)
    else:
        fd = _posixshmem.shm_open(shm_name, os.O_RDONLY, 0)
    try:
        start = offset - offset % mmap.ALLOCATIONGRANULARITY
        with mmap.mmap(fd, offset - start + size, mmap.MAP_SHARED, mmap.PROT_READ, offset=start) as mem:
            return bytes(mem[offset - start:offset - start + size])
    finally:
        os.close(fd)


def run_bare(system, syms, max_ticks):
    import m5
    from m5.objects import Root
    from _m5.drain import DrainManager

    def simulate(ticks=None):
        remaining = max_ticks - m5.curTick()
        if remaining <= 0:
            raise ValueError("max-ticks reached before a complete bare-metal result")
        event = m5.simulate(min(remaining, ticks) if ticks is not None else remaining)
        if m5.curTick() >= max_ticks:
            raise ValueError("max-ticks reached before a complete bare-metal result")
        return event

    def drain():
        # m5.drain() hides exit events and calls unbounded simulate(). Use the
        # same drain manager with the remaining budget on every simulate call.
        manager = DrainManager.instance()
        while not manager.isDrained():
            if manager.tryDrain():
                break
            event = simulate()
            if event.getCause() != "Finished drain":
                raise ValueError(f"unexpected event during drain: {event.getCause()}")
            # Finished drain clears the outstanding count. tryDrain() must
            # run again to set the manager state and check all objects.

    roi_ticks = []
    while True:
        event = simulate()
        if event.getCause() != "simpoint starting point found":
            raise ValueError(f"simulation stopped before tohost_exit: {event.getCause()}")
        pc = system.pc_tracker.getCurrentPcCountPair().get_pc()
        if pc == syms["setStats"][0]:
            roi_ticks.append(int(m5.curTick()))
            if len(roi_ticks) == 1:
                m5.stats.reset()
            elif len(roi_ticks) == 2:
                m5.stats.dump()
            else:
                raise ValueError("expected exactly two setStats entries")
        elif pc == syms["tohost_exit"][0]:
            break
        else:
            raise ValueError("unexpected PC tracker event")
    if len(roi_ticks) != 2 or roi_ticks[1] <= roi_ticks[0]:
        raise ValueError("missing or invalid setStats ROI markers")
    # The tohost store follows the entry marker. Drain before each memory read.
    # Each retry runs at most 1000 cycles. The global budget also covers drain.
    tohost = 0
    for _ in range(100):
        drain()
        m5.memWriteback(Root.getInstance())
        tohost, = struct.unpack("<Q", read_guest(system.shared_backstore, syms["tohost"][0], 8))
        if tohost:
            break
        simulate(1_000_000)
    if not tohost & 1:
        raise ValueError("tohost did not contain an odd exit value")
    cycles, instret = struct.unpack("<QQ", read_guest(system.shared_backstore, syms["bench_stats"][0], 16))
    if cycles <= 0 or instret <= 0:
        raise ValueError("bench_stats must contain positive ROI cycles and instret")
    return {"tohost": tohost, "exit_code": tohost >> 1, "roi": "setStats",
            "bench_stats": {"cycles": cycles, "instret": instret}, "roi_ticks": roi_ticks}


def write_result(path, result):
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, indent=2) + "\n")
    temporary.replace(path)


def main():
    import m5
    from m5.objects import Root

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("--description", required=True, type=Path)
    parser.add_argument("--max-ticks", type=int, default=DEFAULT_MAX_TICKS,
                        help="total tick budget, including exit-store drain (1 ps per tick)")
    args = parser.parse_args()
    output = Path(m5.options.outdir) / "bare.json"
    # Invalidate an old result before validation or simulation can fail.
    write_result(output, {"exit_code": None, "error": "run did not complete"})
    try:
        if not 0 < args.max_ticks < 2**64:
            raise ValueError("max-ticks must be between 1 and 2**64 - 1")
        description = load_description(args.description)
        syms = elf_symbols(args.binary)
        system = make_system(description, args.binary, syms)
        root = Root(full_system=True, system=system)
        m5.ticks.setGlobalFrequency("1ps")
        m5.instantiate()
        result = run_bare(system, syms, args.max_ticks)
    except (ValueError, OSError, TypeError, AttributeError, UnicodeError) as error:
        write_result(output, {"exit_code": None, "error": str(error)})
        parser.exit(1, f"model: {error}\n")
    write_result(output, result)
    print(json.dumps(result))
    if result["exit_code"] != 0:
        raise SystemExit(1)


if __name__ == "__m5_main__":
    main()
