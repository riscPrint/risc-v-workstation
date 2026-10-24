"""Second, offline checker over Sail 0.15's public textual trace interface."""
from pathlib import Path
import re
import tempfile
from rvw.common.proc import run_group
from rvw.common.riscv import decode
from .checker import ReferenceEnded, counter_read
from .trace import Trace
from .elf import Elf
from .sail_config import prepare_config

INSTR = re.compile(r"^\[(\d+)\] \[([A-Z]+)\]: (0x[0-9a-fA-F]+) \((0x[0-9a-fA-F]+)\) (.*)")
# Sail prints S-mode as HS when its H extension is on; VS/VU (virtualized) are not represented.
MODES = {"M": 3, "S": 1, "HS": 1, "U": 0}
EPC = re.compile(r"^CSR [ms]epc \(0x[0-9a-fA-F]+\) <- (0x[0-9a-fA-F]+)")
HTIF = re.compile(r"^(SUCCESS$|FAILURE: (\d+) \(0x[0-9a-fA-F]+\)$)")
# Interrupts whose pending bit only software can set (no Sstc): Sail takes them where the core
# must, so an offline run can check them. Inputs (MSIP, MTIP, SEIP, MEIP) have core timing.
SOFTWARE_INTERRUPTS = {1: "supervisor-software-interrupt", 5: "supervisor-timer-interrupt"}
INTERRUPTS = {"supervisor-software-interrupt": 1, "machine-software-interrupt": 3,
              "supervisor-timer-interrupt": 5, "machine-timer-interrupt": 7,
              "supervisor-external-interrupt": 9, "machine-external-interrupt": 11}
TRAPPING = re.compile(r"^trapping from ([A-Z]+) to ([A-Z]+) to handle ")
FETCH_FAULTS = {0, 1, 12}   # misaligned fetch, fetch access fault, fetch page fault
REG = re.compile(r"^x(\d+) <- (0x[0-9a-fA-F]+)")
MEM = re.compile(r"^mem\[(R|W|RW),(0x[0-9a-fA-F]+)\] (->|<-) (0x[0-9a-fA-F]+)")
PTW_START = re.compile(r"^PTW: Start, stage=(\w+), level=(\d+), vpn=0x[0-9a-fA-F]+, access_type=(R|W|RW|X), privilege=\w+$")
PTW_STEP = re.compile(r"^PTW: Step, stage=(\w+), level=(\d+), pte=(0x[0-9a-fA-F]+), pte_addr=(0x[0-9a-fA-F]+)$")
PTW_SUCCESS = re.compile(r"^PTW: Success, stage=(\w+), level=(\d+), final_ppn=0x[0-9a-fA-F]+$")
CAUSES = {"misaligned-fetch": 0, "fetch-access-fault": 1, "illegal-instruction": 2,
          "breakpoint": 3, "software-breakpoint": 3, "misaligned-load": 4, "load-access-fault": 5,
          "misaligned-store/amo": 6, "store/amo-access-fault": 7,
          "user-ecall": 8, "supervisor-ecall": 9, "machine-ecall": 11,
          "u-call": 8, "s-call": 9, "m-call": 11,
          "fetch-page-fault": 12, "load-page-fault": 13, "store/amo-page-fault": 15}

# Physical memory attributes of Sail 0.15's default RAM and MMIO regions. The platform gives only
# where RAM and MMIO are; these are what Sail needs to know about each kind.
_NO_MISALIGNED = {"load_store": {"None": None}, "vector": {"None": None}, "amo": "AccessFault", "lrsc": "AccessFault"}
RAM_PMA = {"mem_type": "MainMemory", "cacheable": True, "coherent": True, "executable": True,
           "readable": True, "writable": True, "read_idempotent": True, "write_idempotent": True,
           "misaligned_exceptions": _NO_MISALIGNED, "atomic_support": "AMOCASQ",
           "misaligned_atomicity_granule_size_exp": 4, "vector_misaligned_atomicity_granule_size_exp": 4,
           "reservability": "RsrvEventual", "supports_cbo_zero": True, "supports_pte_read": True,
           "supports_pte_write": True}
MMIO_PMA = {"mem_type": "IOMemory", "cacheable": False, "coherent": True, "executable": False,
            "readable": True, "writable": True, "read_idempotent": False, "write_idempotent": False,
            "misaligned_exceptions": _NO_MISALIGNED, "atomic_support": "AMONone",
            "misaligned_atomicity_granule_size_exp": 0, "vector_misaligned_atomicity_granule_size_exp": 0,
            "reservability": "RsrvNone", "supports_cbo_zero": False, "supports_pte_read": False,
            "supports_pte_write": False}


def memory_regions(platform):
    """Sail `memory.regions` for the platform's map: RAM as main memory, MMIO as I/O, nothing
    else (Sail's default map has 2 GiB of RAM and a ROM the core may not have). A map Sail cannot
    represent (a region that is not page aligned) is an error. Sail itself validates the rest
    (its CLINT and test interrupt device must lie in an I/O region, regions within physaddr_bits)."""
    regions = []
    for kind, ranges, pma in (("RAM", platform.ram, RAM_PMA), ("MMIO", platform.mmio, MMIO_PMA)):
        for base, size in ranges:
            if base % 4096 or size % 4096:
                raise ValueError(f"Sail cannot represent the {kind} region {base:#x}+{size:#x}: "
                                 "Sail memory regions must be page aligned")
            regions.append({"base": {"len": 64, "value": hex(base)}, "size": {"len": 64, "value": hex(size)},
                            "attributes": pma, "include_in_device_tree": kind == "RAM"})
    return sorted(regions, key=lambda r: int(r["base"]["value"], 16))


def bits(value, hi, lo):
    return (value >> lo) & ((1 << (hi - lo + 1)) - 1)


def memory_operand(insn, xlen):
    """(rs1, offset) of a scalar load, store or AMO, or None. Compressed funct3 3 and 7 are
    c.ld/c.sd/c.ldsp/c.sdsp on RV64 (doubleword offset) and c.flw/c.fsw/c.flwsp/c.fswsp on RV32
    (word offset, like c.lw)."""
    word = (2, 6, 3, 7) if xlen == 32 else (2, 6)
    if insn & 3 == 3:
        opcode = insn & 0x7f
        if opcode in (0x03, 0x07):                       # LOAD, LOAD-FP: I-immediate
            imm = insn >> 20
        elif opcode in (0x23, 0x27):                     # STORE, STORE-FP: S-immediate
            imm = (bits(insn, 31, 25) << 5) | bits(insn, 11, 7)
        elif opcode == 0x2f:                             # AMO, LR, SC
            imm = 0
        else:
            return None
        return bits(insn, 19, 15), imm - (1 << 12) if imm >> 11 else imm
    quadrant, funct3 = insn & 3, bits(insn, 15, 13)
    if quadrant == 0 and funct3 in (1, 2, 3, 5, 6, 7):   # c.fld c.lw c.ld/c.flw c.fsd c.sw c.sd/c.fsw
        if funct3 in word:
            imm = (bits(insn, 12, 10) << 3) | (bits(insn, 6, 6) << 2) | (bits(insn, 5, 5) << 6)
        else:
            imm = (bits(insn, 12, 10) << 3) | (bits(insn, 6, 5) << 6)
        return 8 + bits(insn, 9, 7), imm
    if quadrant == 2 and funct3 in (1, 2, 3):            # c.fldsp c.lwsp c.ldsp/c.flwsp
        if funct3 in word:
            imm = (bits(insn, 12, 12) << 5) | (bits(insn, 6, 4) << 2) | (bits(insn, 3, 2) << 6)
        else:
            imm = (bits(insn, 12, 12) << 5) | (bits(insn, 6, 5) << 3) | (bits(insn, 4, 2) << 6)
        return 2, imm
    if quadrant == 2 and funct3 in (5, 6, 7):            # c.fsdsp c.swsp c.sdsp/c.fswsp
        if funct3 in word:
            imm = (bits(insn, 12, 9) << 2) | (bits(insn, 8, 7) << 6)
        else:
            imm = (bits(insn, 12, 10) << 3) | (bits(insn, 9, 7) << 6)
        return 2, imm
    return None


def memory_address(effect, xlen):
    """Sail logs physical addresses; C2 holds the virtual one (rs1 + offset, before the step).
    The caller checks that the page offsets agree, so a wrong decoding fails closed."""
    operand = memory_operand(effect["insn"], xlen)
    if operand is None:
        raise ValueError(f"Sail memory access by a non-memory instruction {effect['insn']:#x}")
    rs1, offset = operand
    return (effect["before"][rs1] + offset) & ((1 << xlen) - 1)


def memory_direction(insn, xlen):
    """Use the shared decoder to distinguish loads, stores, LR, SC and AMOs."""
    instruction = decode(insn, xlen)
    if instruction.cls in ("load", "store"):
        return "R" if instruction.cls == "load" else "W"
    if instruction.cls == "atomic":
        return ("R" if instruction.mnemonic.startswith("lr.") else
                "W" if instruction.mnemonic.startswith("sc.") else "RW")
    raise ValueError(f"Sail cannot attribute memory access for instruction {insn:#x}")


def _page_write(walk, match, effect, xlen):
    """Recognize only the immediate, validated A/D update of a successful leaf walk."""
    direction, address, arrow, data = match.groups()
    addr, width, old = walk["read"]
    if arrow != "<-" or int(address, 16) != addr:
        return False
    new = int(data, 16)
    expected = old | 0x40 | (0x80 if "W" in walk["access"] else 0)
    if (direction != "W" or (len(data) - 2) // 2 != width or width != xlen // 8
            or addr % width or not old & 1 or not old & 0xa
            or new != expected or new == old):
        raise ValueError("Sail page-table write is not a validated A/D update")
    if walk["access"] != "X":
        if effect is None or memory_direction(effect["insn"], xlen) != walk["access"]:
            raise ValueError("Sail page-table access direction does not match instruction")
        if "W" in walk["access"] and addr & 0xfff == memory_address(effect, xlen) & 0xfff:
            raise ValueError("Sail page-table write attribution is ambiguous")
    return True


def parse(lines, xlen=64):
    for effect in _parse(lines, xlen):
        accesses = effect.pop("accesses", {"r": [], "w": []})
        if accesses["r"] or accesses["w"]:
            vaddr = memory_address(effect, xlen)
            direction = memory_direction(effect["insn"], xlen)
            for field in ("r", "w"):
                own = accesses[field]
                if len(own) > 1 or own and field.upper() not in direction:
                    raise ValueError("Sail memory trace exceeds scalar C2 format or access direction")
                if own:
                    addr, width, data = own[0]
                    if addr & 0xfff != vaddr & 0xfff:
                        raise ValueError(f"Sail physical address {addr:#x} does not match virtual address {vaddr:#x}")
                    effect[f"mem_{field}mask"] = (1 << width) - 1
                    effect[f"mem_{field}data"] = data
            effect["mem_addr"] = vaddr
        effect.pop("before", None)
        yield effect


def _parse(lines, xlen):
    """Yield one complete effect when the following instruction reveals next PC and the
    mode after the step (`mode_after`). A taken interrupt yields an effect with `intr` set
    (its pending instruction first, with the interrupted PC from the trap's xepc write). HTIF
    termination yields {"end": "pass"|"fail"} after the last instruction."""
    regs, current, interrupt = [0]*32, None, None
    end = None
    page_walk, page_update = None, None
    # --trace-step ends every step with a blank line. An exception in a step that has no
    # instruction line is a fetch fault (Sail fetched nothing): it is a step of its own, as in
    # Spike and RVFI, not an exception of the previous instruction.
    in_step = True
    trap_from = None    # privilege before the last "trapping from X to Y" line
    fetch_fault = None  # a fetch fault waiting for its xepc write (its PC)
    for line in lines:
        if not line.strip():
            in_step = False
            page_walk, page_update = None, None
            continue
        match = TRAPPING.match(line)
        if match:
            trap_from = match[1]
            continue
        if line.startswith("PTW: Start"):
            match = PTW_START.match(line.strip())
            if not match or match[1] != "S_Stage":
                raise ValueError("unsupported Sail page-table walk")
            page_walk = {"access": match[3], "read": None, "step": None}
            page_update = None
            continue
        if line.startswith("PTW: Step"):
            match = PTW_STEP.match(line.strip())
            if not match or not page_walk or match[1] != "S_Stage":
                raise ValueError("Sail page-table step without walk context")
            read = page_walk["read"]
            if read is None or (read[0], read[2]) != (int(match[4], 16), int(match[3], 16)):
                raise ValueError("Sail page-table step does not match its read")
            page_walk["step"] = match[2]
            continue
        if line.startswith("PTW: Success"):
            match = PTW_SUCCESS.match(line.strip())
            if (not match or not page_walk or match[1] != "S_Stage"
                    or page_walk["step"] != match[2]):
                raise ValueError("Sail page-table success without validated leaf context")
            page_update, page_walk = page_walk, None
            continue
        if line.startswith("PTW:"):
            # A failed walk has no validated A/D write.
            page_walk, page_update = None, None
            continue
        match = MEM.match(line)
        if page_walk and match:
            direction, addr, arrow, data = match.groups()
            if direction != "R" or arrow != "->" or (len(data) - 2) // 2 != xlen // 8:
                raise ValueError("unsupported Sail page-table read")
            page_walk["read"] = (int(addr, 16), (len(data) - 2) // 2, int(data, 16))
            page_walk["step"] = None
            continue
        if page_update is not None and (match or line.startswith("mem[")):
            walk, page_update = page_update, None
            if match and _page_write(walk, match, current, xlen):
                continue
        match = INSTR.match(line)
        if match:
            page_walk, page_update = None, None
            _, privilege, pc, insn, disasm = match.groups()
            if privilege not in MODES:
                raise ValueError(f"unsupported Sail privilege [{privilege}] (virtualized modes are not represented)")
            mode = MODES[privilege]
            in_step = True
            if interrupt is not None:
                raise ValueError("Sail interrupt trace without an xepc write")
            if fetch_fault is not None:
                raise ValueError("Sail fetch fault without an xepc write")
            if current:
                current["pc_next"] = int(pc, 16)
                current["mode_after"] = mode
                yield current
            current = dict(pc=int(pc, 16), insn=int(insn, 16), mode=mode,
                           rd=0, rd_wdata=0, mem_addr=0, mem_rmask=0, mem_wmask=0, mem_rdata=0,
                           mem_wdata=0, mem_fault=0, trap=0, intr=0, cause=0, tval=0,
                           halted=0, disasm=disasm.strip(), regs=list(regs), before=list(regs),
                           accesses={"r": [], "w": []})
            continue
        match = HTIF.match(line.strip())
        if match:
            end = "pass" if match[1] == "SUCCESS" else "fail"
            continue
        if "handling int#" in line:
            name = re.search(r"handling int#(\S+) at priv ([A-Z]+)", line)
            if not name or name[1] not in INTERRUPTS or name[2] not in MODES:
                raise ValueError(f"unsupported Sail interrupt trace: {line.strip()}")
            interrupt = {"code": INTERRUPTS[name[1]], "mode": MODES[name[2]]}
            continue
        if not in_step and fetch_fault is None and "handling exc#" in line:
            match = re.search(r"handling exc#(\S+).*tval=(0x[0-9a-fA-F]+)", line)
            if not match or CAUSES.get(match[1]) not in FETCH_FAULTS or trap_from not in MODES:
                raise ValueError(f"unsupported Sail exception outside an instruction: {line.strip()}")
            fetch_fault = dict(pc_next=0, insn=0, mode=MODES[trap_from], rd=0, rd_wdata=0, mem_addr=0,
                               mem_rmask=0, mem_wmask=0, mem_rdata=0, mem_wdata=0, mem_fault=1, trap=1,
                               intr=0, cause=CAUSES[match[1]], tval=int(match[2], 16), halted=0,
                               disasm="<instruction fetch fault>", accesses={"r": [], "w": []})
            in_step = True
            continue
        if fetch_fault is not None:
            match = EPC.match(line)
            if match:
                epc = int(match[1], 16)
                if current:
                    current["pc_next"] = epc
                    current["mode_after"] = fetch_fault["mode"]
                    yield current
                current = dict(fetch_fault, pc=epc, regs=list(regs), before=list(regs))
                fetch_fault = None
            continue
        if interrupt is not None:
            match = EPC.match(line)
            if match:
                epc = int(match[1], 16)
                if current:
                    current["pc_next"] = epc
                    current["mode_after"] = interrupt["mode"]
                    yield current
                    current = None
                yield dict(pc=epc, pc_next=0, insn=0, mode=interrupt["mode"], rd=0, rd_wdata=0, mem_addr=0,
                           mem_rmask=0, mem_wmask=0, mem_rdata=0, mem_wdata=0, mem_fault=0, trap=1, intr=1,
                           cause=(1 << (xlen - 1)) | interrupt["code"], tval=0, halted=0,
                           disasm=f"<interrupt {interrupt['code']}>", regs=list(regs), mode_after=None)
                interrupt = None
            continue
        if current is None:
            continue
        match = REG.match(line)
        if match:
            rd, data = int(match[1]), int(match[2], 16)
            if rd:
                if current["rd"]:
                    raise ValueError("Sail reported multiple integer writes")
                regs[rd] = data
                current.update(rd=rd, rd_wdata=data, regs=list(regs))
        match = MEM.match(line)
        if match:
            direction, addr, arrow, data = match.groups()
            width = (len(data)-2)//2
            field = "r" if arrow == "->" else "w"
            if width > 8:
                raise ValueError("Sail memory trace exceeds scalar C2 format")
            current["accesses"][field].append((int(addr, 16), width, int(data, 16)))
        if "handling exc#" in line:
            match = re.search(r"handling exc#(\S+).*tval=(0x[0-9a-fA-F]+)", line)
            if not match or match[1] not in CAUSES:
                raise ValueError(f"unsupported Sail exception trace: {line.strip()}")
            cause = CAUSES[match[1]]
            current.update(trap=1, cause=cause, tval=int(match[2], 16),
                           mem_fault=int(cause in (1, 5, 7, 12, 13, 15)))
    if interrupt is not None:
        raise ValueError("Sail interrupt trace without an xepc write")
    if fetch_fault is not None:
        raise ValueError("Sail fetch fault without an xepc write")
    if current:
        # Sail stops immediately on a tohost write. Its last instruction must
        # be a store; for other termination we require one lookahead instruction.
        if current["accesses"]["w"] and not current["trap"]:
            current["pc_next"] = current["pc"] + (2 if current["insn"] & 3 != 3 else 4)
            current["mode_after"] = current["mode"]
            yield current
            if end:
                yield {"end": end}


class Sail:
    """Offline reference. ISA, PMP and memory settings come from the platform. The model must
    confirm its effective ISA before executing. `sail_overrides` tune other Sail parameters
    after --sail-config or Sail's default. `illegal_insn_tval` uses Sail's own
    `base.xtval_nonzero.illegal_instruction` setting. With `mode_after_change`, `mode()` is the
    mode of Sail's next traced instruction). It cannot take values from the core (no `set_reg`),
    so a trace that needs synchronization is an error, not a match. It takes only software
    interrupts (SOFTWARE_INTERRUPTS) itself; a trace with another interrupt is rejected. At
    Sail's HTIF termination `step` raises ReferenceEnded: the comparison ends there; when the
    core trace ends at that point, `terminated()` gives Sail's status."""
    name = "sail"

    def __init__(self, platform, elf, trace_path, executable, config=None, timeout=120, *,
                 env, default_config):
        self.temp = tempfile.TemporaryDirectory(prefix="rvw-sail-")
        self.log = None
        try:
            self._initialize(platform, elf, trace_path, executable, config, timeout, env, default_config)
        except BaseException:
            self.close()
            raise

    def _initialize(self, platform, elf, trace_path, executable, config, timeout, env, default_config):
        self.platform = platform
        image = Elf(elf)
        if image.xlen != platform.xlen or image.entry != platform.reset_pc:
            raise ValueError("Sail requires matching ELF XLEN and reset_pc at the ELF entry")
        platform.check_segments(image)
        memory_override = platform.sail_overrides.get("memory")
        if isinstance(memory_override, dict) and "regions" in memory_override:
            raise ValueError("sail_overrides must not set memory.regions: Sail's regions come from the platform's ram and mmio")
        regions = memory_regions(platform)
        trace = Trace(trace_path)
        try:
            steps = 1
            last_trapped = False
            for r in trace:
                if r.get("event") == "trap":
                    if r["intr"]:
                        code = r["cause"] & ~(1 << (platform.xlen - 1))
                        if code not in SOFTWARE_INTERRUPTS:
                            raise ValueError(f"Sail offline mode rejects interrupt {code}: only software "
                                             f"interrupts ({', '.join(SOFTWARE_INTERRUPTS.values())}) are deterministic")
                        continue   # not an instruction step
                    if not last_trapped:
                        steps += 1
                    last_trapped = False
                elif "event" not in r:
                    if counter_read(r["insn"]) or platform.mmio_read(r):
                        raise ValueError("Sail offline mode rejects nondeterministic counter/MMIO reads")
                    steps += 1
                    last_trapped = r["trap"]
        finally:
            trace.close()
        self.last_mode = None
        try:
            effective = prepare_config(platform, executable, config, self.temp.name,
                                       regions, timeout, env=env, default_config=default_config)
            command = [str(executable), "--trace-instr", "--trace-gpr", "--trace-mem", "--trace-exception",
                       "--trace-interrupt", "--trace-csr", "--trace-ptw", "--trace-step", "--inst-limit", str(steps)]
            command += ["--config", str(effective)]
            command.append(str(Path(elf).resolve()))
            logpath = Path(self.temp.name) / "trace.txt"
            with logpath.open("w") as log:
                proc = run_group(command, stdout=log, stderr=log, timeout=timeout, env=env)
            if proc.timed_out:
                raise ValueError(f"Sail did not finish within {timeout} s")
            tail = logpath.read_text()[-2000:]
            htif_failure = any(HTIF.match(l.strip()) and l.startswith("FAILURE") for l in tail.splitlines())
            if proc.returncode and not htif_failure:
                raise ValueError(f"Sail exited {proc.returncode}: {tail}")
            self.log = logpath.open()
            self.effects = iter(parse(self.log, platform.xlen))
            self.peeked = None   # the next effect, read by terminated() and not yet stepped
        except BaseException:
            self.close()
            raise

    def step(self, interrupt=0, mmio=None):
        """Sail's next step. With `interrupt` (a core trap event) Sail must have taken that
        interrupt itself; the checker compares the cause, and a step without one is a mismatch."""
        if mmio:
            raise ValueError("Sail offline mode cannot synchronize external state")
        try:
            effect, self.peeked = self.peeked or next(self.effects), None
        except StopIteration as exc:
            raise ValueError("Sail trace ended before the core trace (or lacks next-PC lookahead)") from exc
        if "end" in effect:
            raise ReferenceEnded(effect["end"])
        if interrupt and not effect["intr"]:
            # The core took an interrupt here and Sail did not: keep Sail's step for the
            # report, marked as no trap so the checker reports the difference.
            effect = dict(effect, trap=0)
        if not effect["intr"]:
            self.last_mode = effect["mode_after"]
        return self.platform.normalize_effect(effect)

    def terminated(self):
        """Sail's HTIF status ("pass" or "fail") if Sail's run ended right after the last step,
        else None. The checker calls this at the end of the core trace, where no further step
        would raise ReferenceEnded (a core that stops at the tohost store itself)."""
        if self.peeked is None:
            try:
                self.peeked = next(self.effects)
            except StopIteration:
                return None
        return self.peeked.get("end")

    def mode(self):
        """Privilege mode after the last step: the mode of Sail's next traced instruction."""
        if self.last_mode is None:
            raise ValueError("Sail has not stepped")
        return self.last_mode

    def close(self):
        if self.log is not None:
            self.log.close()
        self.temp.cleanup()
