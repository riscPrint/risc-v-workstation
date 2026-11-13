"""Explicit platform inputs; no core-specific behavior in the checker."""
import json
import re
from dataclasses import dataclass, field, fields
from pathlib import Path


def number(value):
    if type(value) not in (str, int):
        raise ValueError("integer or integer string expected")
    return int(value, 0) if isinstance(value, str) else int(value)


PMPADDR0 = 0x3b0
# Interrupts whose pending bit only software sets (no Sstc): never a platform input.
SOFTWARE_ONLY_IRQS = (1, 5)


def parse_csr_masks(items, xlen, pmp_regions):
    """{csr: mask} from {"0x301": "0x6", "0x3b0-0x3b7": "0xffffffffc0000000"}.

    A mask holds the implementation-defined bits of a CSR; all other bits compare strictly.
    """
    if not isinstance(items, dict):
        raise ValueError("csr_masks must be an object of CSR (or range) to mask")
    out = {}
    for key, value in items.items():
        lo, _, hi = str(key).partition("-")
        lo, hi = int(lo, 0), int(hi or lo, 0)
        mask = number(value)
        if not 0 <= lo <= hi < 4096:
            raise ValueError(f"invalid csr_masks entry {key!r}")
        if not 0 < mask < 1 << xlen:
            raise ValueError(f"csr_masks {key!r}: mask must be nonzero and fit XLEN")
        for csr in range(lo, hi + 1):
            if PMPADDR0 + pmp_regions <= csr < PMPADDR0 + 64:
                raise ValueError(f"csr_masks {key!r}: pmpaddr{csr - PMPADDR0} exceeds pmp_regions={pmp_regions}")
            if csr in out:
                raise ValueError(f"csr_masks: CSR {csr:#x} listed twice")
            out[csr] = mask
    return out


@dataclass
class Platform:
    name: str
    xlen: int
    isa: str
    reset_pc: int
    ram: list[tuple[int, int]]
    mmio: list[tuple[int, int]]
    pmp_regions: int = 8
    aligned_mem: bool = False
    reference_isa: str | None = None
    illegal_insn_tval: str = "insn"   # what the core writes to xtval on an illegal instruction: "insn" or "zero"
    mode_after_change: bool = False     # known trace quirk: an instruction that changes mode (xRET, trap) is reported in the new mode
    trace_from_reset: bool = True       # false: the trace starts after reset, so the first instret read sets the offset
    csr_masks: dict = field(default_factory=dict)  # {csr: mask of implementation-defined bits}; a read takes those bits from the core
    sail_overrides: dict = field(default_factory=dict)  # Sail config override (JSON object) for this core
    irq_input_latency: int = 4          # cycles an interrupt input level may take to reach mip (C2 irq events)
    # Interrupt causes (mip bits) driven by platform inputs. Only these may be injected into a reference
    # at a core's trap event; any other interrupt (SSIP, STIP: set by software) must come from the
    # reference's own pending and enable state. Default: MSIP, MTIP, SEIP, MEIP.
    irq_inputs: list = field(default_factory=lambda: [3, 7, 9, 11])

    privilege_modes: str = "MSU"
    misaligned: dict = field(default_factory=lambda: {
        "load": "trap", "store": "trap", "atomic": "trap",
        "split_page": "refuse", "split_bus": "refuse"})
    endianness: dict = field(default_factory=lambda: {
        "instruction": "little", "data": "little", "page_table": "little", "device": "little"})
    absent_pmp_csrs: str = "trap"
    pmp_granularity: int = 4  # minimum PMP region size in bytes
    cheri: dict | None = None
    reference_extensions: list = field(default_factory=list)
    ecall_tval: str = "zero"
    sail_reference_isa: str | None = None
    memory_read_convention: str = "architectural"
    scalar_split_ram: bool = False
    fcsr_reset: str = "zero"

    @classmethod
    def load(cls, core, path=None):
        path = Path(path) if path else Path(__file__).parent / "configs" / f"{core}.json"
        obj = json.loads(path.read_text())
        if obj.get("review_required"):
            raise ValueError("Review the scaffold platform against the core specification before removing review_required.")
        if obj.get("schema") == "rvw.soc/1":
            from rvw.soc.model import load, platform
            obj = platform(load(path))
        unknown = obj.keys() - {f.name for f in fields(cls)} - {"schema", "review_required"}
        if unknown:
            raise ValueError(f"unknown cosim platform settings: {sorted(unknown)}")
        if "schema" in obj and obj["schema"] != "rvw.cosim-platform/1":
            raise ValueError("unsupported cosim platform schema")
        def ranges(key):
            return [(number(r["base"]), number(r["size"])) for r in obj[key]]
        p = cls(obj["name"], obj["xlen"], obj["isa"], number(obj["reset_pc"]),
                ranges("ram"), ranges("mmio"), obj.get("pmp_regions", 8), obj.get("aligned_mem", False), obj.get("reference_isa"),
                obj.get("illegal_insn_tval", "insn"), obj.get("mode_after_change", False),
                obj.get("trace_from_reset", True))
        p.scalar_split_ram = obj.get('scalar_split_ram', False)
        if type(p.scalar_split_ram) is not bool:
            raise ValueError('scalar_split_ram must be a boolean')
        p.fcsr_reset = obj.get('fcsr_reset', 'zero')
        if p.fcsr_reset not in ('zero', 'unspecified'):
            raise ValueError('fcsr_reset must be zero or unspecified')
        if p.fcsr_reset == 'unspecified' and not p.trace_from_reset:
            raise ValueError('unspecified fcsr requires a trace from reset')
        p.memory_read_convention = obj.get('memory_read_convention', 'architectural')
        if p.memory_read_convention not in ('architectural', 'full_word'):
            raise ValueError('memory_read_convention must be architectural or full_word')
        if p.memory_read_convention == 'full_word' and not p.aligned_mem:
            raise ValueError('full_word reads require aligned_mem=true')
        p.sail_reference_isa = obj.get("sail_reference_isa")
        from .cheri import validate as validate_cheri
        p.cheri = validate_cheri(obj.get("cheri"))
        from .custom import validate_extensions
        p.reference_extensions = validate_extensions(obj.get("reference_extensions", []))
        p.privilege_modes = obj.get("privilege_modes", "MSU")
        if p.privilege_modes not in ("M", "MU", "MSU"):
            raise ValueError("privilege_modes must be M, MU or MSU")
        policy_keys = p.misaligned.keys()
        p.misaligned = obj.get("misaligned", p.misaligned)
        if (not isinstance(p.misaligned, dict) or p.misaligned.keys() != policy_keys
                or p.misaligned["load"] not in ("trap", "emulate")
                or p.misaligned["store"] != p.misaligned["load"]
                or p.misaligned["atomic"] != ("trap" if p.misaligned["load"] == "trap" else "access_fault")
                or any(p.misaligned[k] != "refuse" for k in ("split_page", "split_bus"))):
            raise ValueError("unsupported misaligned policy: equal load/store trap or emulate, atomic trap or access_fault respectively, split_page/split_bus refuse required")
        endianness = obj.get("endianness", p.endianness)
        if endianness != p.endianness:
            raise ValueError("only little endianness for instruction, data, page_table and device is supported")
        p.endianness = endianness
        p.absent_pmp_csrs = obj.get("absent_pmp_csrs", "trap")
        if p.absent_pmp_csrs not in ("trap", "read_zero_write_ignored"):
            raise ValueError("absent_pmp_csrs must be trap or read_zero_write_ignored")
        if p.absent_pmp_csrs != "trap" and p.pmp_regions != 0:
            raise ValueError("absent_pmp_csrs read_zero_write_ignored requires pmp_regions=0")
        p.pmp_granularity = obj.get("pmp_granularity", 4)
        if (type(p.pmp_granularity) is not int or not 4 <= p.pmp_granularity <= 1 << (p.xlen - 1)
                or p.pmp_granularity & (p.pmp_granularity - 1)):
            raise ValueError("pmp_granularity must be a power of two from 4 to 2^(XLEN-1) bytes")
        p.ecall_tval = obj.get("ecall_tval", "zero")
        if p.ecall_tval not in ("zero", "insn"):
            raise ValueError("ecall_tval must be zero or insn")
        p.sail_overrides = obj.get("sail_overrides", {})
        if not isinstance(p.sail_overrides, dict):
            raise ValueError("sail_overrides must be a JSON object (a Sail config override)")
        p.irq_input_latency = obj.get("irq_input_latency", 4)
        if type(p.irq_input_latency) is not int or not 0 <= p.irq_input_latency <= 1000:
            raise ValueError("irq_input_latency must be an integer number of cycles (0 to 1000)")
        p.irq_inputs = obj.get("irq_inputs", [3, 7, 9, 11])
        if (not isinstance(p.irq_inputs, list) or len(set(p.irq_inputs)) != len(p.irq_inputs)
                or any(type(c) is not int or not 0 <= c < min(p.xlen, 64) or c in SOFTWARE_ONLY_IRQS
                       for c in p.irq_inputs)):
            raise ValueError("irq_inputs must be a list of distinct interrupt cause codes (< XLEN) driven by "
                             "platform inputs; SSIP (1) and STIP (5) are set by software, not inputs")
        if "csr_sync" in obj:
            raise ValueError("csr_sync took whole CSR values from the core; use csr_masks with the implementation-defined bits")
        if type(p.pmp_regions) is not int or not 0 <= p.pmp_regions <= 64:
            raise ValueError("invalid PMP count")
        p.csr_masks = parse_csr_masks(obj.get("csr_masks", {}), p.xlen, p.pmp_regions)
        if p.absent_pmp_csrs == "read_zero_write_ignored" and any(
                0x3a0 <= csr <= 0x3ef for csr in p.csr_masks):
            raise ValueError("absent PMP CSR values must compare exactly; csr_masks cannot cover them")
        if type(p.mode_after_change) is not bool or type(p.trace_from_reset) is not bool:
            raise ValueError("mode_after_change and trace_from_reset must be boolean")
        if p.illegal_insn_tval not in ("insn", "zero"):
            raise ValueError("illegal_insn_tval must be insn or zero")
        if (p.xlen not in (32, 64) or not isinstance(p.isa, str)
                or not re.fullmatch(r"rv(?:32|64)[a-z0-9_]+", p.isa)
                or not p.isa.startswith(f"rv{p.xlen}")):
            raise ValueError("platform xlen and ISA disagree")
        if p.reference_isa is not None and (not isinstance(p.reference_isa, str)
                or not re.fullmatch(r"rv(?:32|64)[a-z0-9_]+", p.reference_isa)
                or not p.reference_isa.startswith(f"rv{p.xlen}")):
            raise ValueError("invalid reference_isa")
        if p.sail_reference_isa is not None and (not isinstance(p.sail_reference_isa, str)
                or not re.fullmatch(r"rv(?:32|64)[a-z0-9_]+", p.sail_reference_isa)
                or not p.sail_reference_isa.startswith(f"rv{p.xlen}")):
            raise ValueError("invalid sail_reference_isa")
        if type(p.aligned_mem) is not bool:
            raise ValueError("aligned_mem must be boolean")
        if not 0 <= p.reset_pc < 1 << p.xlen:
            raise ValueError("reset PC exceeds XLEN")
        if not 0 <= p.pmp_regions <= 64 or not p.ram:
            raise ValueError("invalid PMP count or empty RAM map")
        ordered = sorted(p.ram + p.mmio)
        for i, (base, size) in enumerate(ordered):
            if base < 0 or size <= 0 or base + size > 1 << p.xlen:
                raise ValueError("invalid memory region")
            if i and ordered[i-1][0] + ordered[i-1][1] > base:
                raise ValueError("overlapping platform regions")
        if any(base % 4096 or size % 4096 for base, size in p.ram):
            raise ValueError("RAM regions must have page-aligned base and size")
        return p

    def describe(self):
        """JSON form, with CSR masks in hex."""
        out = dict(vars(self))
        out["csr_masks"] = {hex(k): hex(v) for k, v in sorted(self.csr_masks.items())}
        return out

    def check_segments(self, image):
        """Every ELF load segment (its file bytes and BSS) lies wholly in one RAM region.
        Shared by all reference models, so none loads a program the platform cannot hold."""
        for addr, _, memsz in image.segments:
            if not any(base <= addr and addr + memsz <= base + size for base, size in self.ram):
                raise ValueError(f"ELF segment {addr:#x}+{memsz:#x} outside configured RAM")

    @property
    def irq_input_mask(self):
        """mip bits of the platform's interrupt inputs."""
        return sum(1 << c for c in self.irq_inputs)

    def is_mmio(self, addr, size):
        return any(base <= addr and addr + size <= base + length for base, length in self.mmio)

    def normalize_record(self, record):
        """Project-declared read bus representation to architectural byte lanes.

        Only ordinary scalar loads use this convention. Stores keep their exact
        strobes. Reject unknown encodings and inconsistent raw bus evidence.
        """
        if self.memory_read_convention != 'full_word' or not record['mem_rmask']:
            return record
        insn = record['insn']
        if insn & 0x7f != 0x03 or record['trap']:
            raise ValueError('full_word read convention requires a nontrapping scalar load')
        width_code = (insn >> 12) & 7
        widths = {0: 1, 1: 2, 2: 4, 4: 1, 5: 2}
        if self.xlen == 64:
            widths.update({3: 8, 6: 4})
        if width_code not in widths:
            raise ValueError('unsupported scalar load width for full_word read')
        size = widths[width_code]
        immediate = insn >> 20
        if immediate & 0x800:
            immediate -= 0x1000
        address = (record['rs1_rdata'] + immediate) & ((1 << self.xlen) - 1)
        bus_bytes = self.xlen // 8
        offset = address % bus_bytes
        if offset + size > bus_bytes or address % size:
            raise ValueError('full_word read convention does not support misaligned loads')
        if (record['mem_addr'] != address - offset
                or record['mem_rmask'] != (1 << bus_bytes) - 1
                or record['mem_wmask']):
            raise ValueError('raw read address or strobes contradict full_word convention')
        if self.is_mmio(address - offset, bus_bytes):
            raise ValueError('full_word MMIO reads need a project device model')
        return {**record, 'mem_rmask': ((1 << size) - 1) << offset}

    def normalize_effect(self, effect):
        if self.aligned_mem and (effect["mem_rmask"] or effect["mem_wmask"]):
            offset = effect["mem_addr"] % (self.xlen//8)
            effect["mem_addr"] -= offset
            for field in ("mem_rmask", "mem_wmask"):
                effect[field] <<= offset
                if effect[field] >= 1 << (self.xlen//8):
                    raise ValueError("memory access crosses an aligned RVFI word")
            for field in ("mem_rdata", "mem_wdata"):
                effect[field] = (effect[field] << (8*offset)) & ((1 << self.xlen)-1)
        return effect

    def mmio_read(self, record):
        mask = record["mem_rmask"]
        if not mask:
            return None
        offset = (mask & -mask).bit_length()-1 if self.aligned_mem else 0
        address = record["mem_addr"] + offset
        size = mask.bit_length()-offset
        if self.is_mmio(address, size):
            return address, record["mem_rdata"] >> (8*offset)
        return None
