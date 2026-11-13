"""Small RV64/RV32 hart model for the Debug Module reference.

It executes RV I + M, Zicsr, the trap and debug instructions and a few compressed
forms. It is a reference for debug behavior, not an ISA simulator: use Spike for
architectural conformance. Unknown encodings raise illegal-instruction traps.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import triggers as trig

M, S, U = 3, 1, 0

# CSR addresses used by the model.
MSTATUS, MISA, MEDELEG, MIE, MTVEC = 0x300, 0x301, 0x302, 0x304, 0x305
MSCRATCH, MEPC, MCAUSE, MTVAL, MIP = 0x340, 0x341, 0x342, 0x343, 0x344
MHARTID, MCYCLE, MINSTRET = 0xf14, 0xb00, 0xb02
TSELECT, TDATA1, TDATA2, TDATA3, TINFO, TCONTROL, MCONTEXT = 0x7a0, 0x7a1, 0x7a2, 0x7a3, 0x7a4, 0x7a5, 0x7a8
DCSR, DPC, DSCRATCH0, DSCRATCH1 = 0x7b0, 0x7b1, 0x7b2, 0x7b3
DEBUG_CSRS = {DCSR, DPC, DSCRATCH0, DSCRATCH1}

# dcsr causes
CAUSE_EBREAK, CAUSE_TRIGGER, CAUSE_HALTREQ, CAUSE_STEP, CAUSE_RESETHALT, CAUSE_GROUP = 1, 2, 3, 4, 5, 6

# Exception causes
ILLEGAL, BREAKPOINT = 2, 3
LOAD_MISALIGNED, LOAD_FAULT, STORE_MISALIGNED, STORE_FAULT = 4, 5, 6, 7
FETCH_FAULT = 1
ECALL = {U: 8, S: 9, M: 11}


class BusError(Exception):
    def __init__(self, kind='error', sberror=2):
        super().__init__(kind)
        self.kind = kind
        self.sberror = sberror


@dataclass
class Region:
    base: int
    size: int
    kind: str = 'ram'          # ram, readonly, error, off
    sberror: int | None = None  # declared system-bus error code for this region

    def contains(self, address, size=1):
        return self.base <= address and address + size <= self.base + self.size


class Memory:
    """Sparse little-endian memory with declared regions. Accesses outside regions fail."""

    def __init__(self, regions):
        self.regions = [r if isinstance(r, Region) else Region(**r) for r in regions]
        self.bytes = {}
        self.log = []   # (source, write, address, size) for concurrency checks

    def region(self, address, size):
        for region in self.regions:
            if region.contains(address, size):
                return region
        return None

    def read(self, address, size, source='hart'):
        region = self.region(address, size)
        if region is None or region.kind in ('error', 'off'):
            kind = region.kind if region else 'unmapped'
            raise BusError(kind, (region.sberror if region and region.sberror else (7 if kind == 'off' else 2)))
        self.log.append((source, False, address, size))
        return int.from_bytes(bytes(self.bytes.get(address + i, 0) for i in range(size)), 'little')

    def write(self, address, size, value, source='hart'):
        region = self.region(address, size)
        if region is None or region.kind != 'ram':
            kind = region.kind if region else 'unmapped'
            raise BusError(kind, (region.sberror if region and region.sberror else (7 if kind == 'off' else 2)))
        self.log.append((source, True, address, size))
        for i in range(size):
            self.bytes[address + i] = (value >> (8 * i)) & 0xff

    def load(self, address, data: bytes):
        for i, b in enumerate(data):
            self.bytes[address + i] = b


class Trap(Exception):
    def __init__(self, cause, tval=0):
        super().__init__(cause)
        self.cause = cause
        self.tval = tval


class DebugEntry(Exception):
    """A trigger with action 1 or an ebreak asked for debug entry."""

    def __init__(self, cause, dpc):
        super().__init__(cause)
        self.cause = cause
        self.dpc = dpc


def sx(value, bits):
    value &= (1 << bits) - 1
    return value - (1 << bits) if value >> (bits - 1) else value


class Hart:
    def __init__(self, memory, *, hartid=0, xlen=64, modes='MSU', reset_pc=0x80000000,
                 trigger_profile=None, debug_version=4):
        self.mem = memory
        self.hartid = hartid
        self.xlen = xlen
        self.mask = (1 << xlen) - 1
        self.modes = set(modes)
        self.reset_pc = reset_pc
        self.debug_version = debug_version
        self.triggers = trig.TriggerUnit(self, trigger_profile or {})
        self.reset()

    # -- state ---------------------------------------------------------------
    def reset(self):
        self.x = [0] * 32
        self.f = [0] * 32          # raw FLEN=64 register bits, for abstract FPR access only
        self.pc = self.reset_pc
        self.mode = M
        self.debug_mode = False
        self.csr = {MSTATUS: 0, MTVEC: 0, MEPC: 0, MCAUSE: 0, MTVAL: 0, MSCRATCH: 0, MIE: 0, MIP: 0,
                    MCYCLE: 0, MINSTRET: 0, DPC: 0, DSCRATCH0: 0, DSCRATCH1: 0}
        self.dcsr = (self.debug_version << 28) | M  # prv=M
        self.triggers.reset()
        self.stepping = False
        self.trap_from = M

    def setx(self, reg, value):
        if reg:
            self.x[reg] = value & self.mask

    def misa(self):
        bits = (1 << 8) | (1 << 12)  # I, M
        bits |= (1 << 18) if S in self._modes_int() else 0
        bits |= (1 << 20) if U in self._modes_int() else 0
        bits |= 1 << 2   # C (subset)
        return ((2 if self.xlen == 64 else 1) << (self.xlen - 2)) | bits

    def _modes_int(self):
        return {dict(M=M, S=S, U=U)[m] for m in self.modes}

    # -- CSRs ----------------------------------------------------------------
    def read_csr(self, address, *, debugger=False):
        debug = self.debug_mode or debugger
        if address in DEBUG_CSRS:
            if not debug:
                raise Trap(ILLEGAL)
            return self.dcsr if address == DCSR else self.csr[address]
        if address in (TSELECT, TDATA1, TDATA2, TDATA3, TINFO, TCONTROL, MCONTEXT):
            if self.mode != M and not debug:
                raise Trap(ILLEGAL)
            return self.triggers.read(address)
        if address == MISA:
            return self.misa()
        if address == MHARTID:
            return self.hartid
        if address == MEDELEG:
            return 0
        if address in self.csr:
            if self.mode != M and not debug and (address >> 8) & 3 == 3:
                raise Trap(ILLEGAL)
            return self.csr[address]
        raise Trap(ILLEGAL)

    def write_csr(self, address, value, *, debugger=False):
        value &= self.mask
        debug = self.debug_mode or debugger
        if (address >> 10) & 3 == 3:
            raise Trap(ILLEGAL)   # read-only CSR
        if address in DEBUG_CSRS:
            if not debug:
                raise Trap(ILLEGAL)
            if address == DCSR:
                self.write_dcsr(value)
            else:
                self.csr[address] = value & ~1 if address == DPC else value
            return
        if address in (TSELECT, TDATA1, TDATA2, TDATA3, TINFO, TCONTROL, MCONTEXT):
            if self.mode != M and not debug:
                raise Trap(ILLEGAL)
            self.triggers.write(address, value, debug=debug)
            return
        if address in (MISA, MEDELEG):
            return
        if address not in self.csr:
            raise Trap(ILLEGAL)
        if self.mode != M and not debug:
            raise Trap(ILLEGAL)
        if address == MSTATUS:
            mpp = (value >> 11) & 3
            if mpp not in self._modes_int():
                value = (value & ~(3 << 11)) | (M << 11)
            value &= (1 << 3) | (1 << 7) | (3 << 11) | (1 << 8) | (1 << 1) | (1 << 5)
        elif address == MIP:
            value = (self.csr[MIP] & ~2) | (value & 2)   # only SSIP is software-writable
        elif address == MIE:
            value &= 0xaaa
        elif address in (MEPC,):
            value &= ~1
        elif address == MTVEC:
            value &= ~3
        self.csr[address] = value

    def write_dcsr(self, value):
        writable = (1 << 15) | (1 << 2) | (1 << 11) | (1 << 10) | (1 << 9) | 3
        if S in self._modes_int():
            writable |= 1 << 13
        if U in self._modes_int():
            writable |= 1 << 12
        new = (self.dcsr & ~writable) | (value & writable)
        if (new & 3) not in self._modes_int() or (new & 3) == 2:
            new = (new & ~3) | (self.dcsr & 3)
        self.dcsr = new

    # -- execution -----------------------------------------------------------
    def fetch(self, pc):
        if pc & 1:
            raise Trap(0, pc)
        try:
            low = self.mem.read(pc, 2)
            if low & 3 != 3:
                return low, 2
            return low | (self.mem.read(pc + 2, 2) << 16), 4
        except BusError:
            raise Trap(FETCH_FAULT, pc) from None

    def load(self, address, size, signed=True):
        self.triggers.check_access(address, size, load=True, before=True)
        if address % size:
            raise Trap(LOAD_MISALIGNED, address)
        try:
            value = self.mem.read(address, size)
        except BusError:
            raise Trap(LOAD_FAULT, address) from None
        self.triggers.check_access(address, size, load=True, data=value)
        return sx(value, size * 8) & self.mask if signed else value

    def store(self, address, size, value):
        value &= (1 << (8 * size)) - 1
        self.triggers.check_access(address, size, store=True, before=True, data=value)
        if address % size:
            raise Trap(STORE_MISALIGNED, address)
        try:
            self.mem.write(address, size, value)
        except BusError:
            raise Trap(STORE_FAULT, address) from None
        self.triggers.check_access(address, size, store=True, data=value)

    def step(self):
        """Execute one instruction in normal mode. Returns a debug-entry cause or None."""
        assert not self.debug_mode
        pc = self.pc
        pending = self.csr[MIP] & self.csr[MIE]
        enabled = self.mode < M or (self.csr[MSTATUS] >> 3) & 1
        if pending and enabled and not (self.stepping and not (self.dcsr >> 11) & 1):
            number = (pending & -pending).bit_length() - 1
            self.take_trap((1 << (self.xlen - 1)) | number, 0, pc)
            try:
                self.triggers.trap_taken(number, interrupt=True)
            except DebugEntry as entry:
                return self.enter_debug(entry.cause, entry.dpc)
            return None
        try:
            self.triggers.check_execute(pc)
            insn, length = self.fetch(pc)
            self.next_pc = (pc + length) & self.mask
            self.execute(insn, length)
            self.pc = self.next_pc
            self.csr[MINSTRET] = (self.csr[MINSTRET] + 1) & self.mask
            self.triggers.retired()
            self.triggers.after()
        except DebugEntry as entry:
            return self.enter_debug(entry.cause, entry.dpc)
        except Trap as trap:
            self.take_trap(trap.cause, trap.tval, pc)
            try:
                self.triggers.trap_taken(trap.cause, interrupt=False)
            except DebugEntry as entry:
                return self.enter_debug(entry.cause, entry.dpc)
        return None

    def take_trap(self, cause, tval, pc):
        status = self.csr[MSTATUS]
        mie = (status >> 3) & 1
        status = (status & ~((1 << 7) | (3 << 11) | (1 << 3))) | (mie << 7) | (self.mode << 11)
        self.csr[MSTATUS] = status
        self.csr[MEPC] = pc
        self.csr[MCAUSE] = cause
        self.csr[MTVAL] = tval & self.mask
        self.trap_from = self.mode
        self.mode = M
        self.triggers.on_trap()
        self.pc = self.csr[MTVEC] & ~3

    def enter_debug(self, cause, dpc):
        self.csr[DPC] = dpc & self.mask
        self.dcsr = (self.dcsr & ~((7 << 6) | 3)) | (cause << 6) | self.mode
        self.mode = M
        self.debug_mode = True
        return cause

    def leave_debug(self):
        self.debug_mode = False
        self.mode = self.dcsr & 3
        if self.mode != M:
            self.csr[MSTATUS] &= ~(1 << 17)   # MPRV clears when leaving to a lower mode
        self.pc = self.csr[DPC]

    def run_debug(self, words, base):
        """Execute program-buffer words in Debug Mode. Returns None on ebreak, or the exception."""
        assert self.debug_mode
        code = {}
        for i, word in enumerate(words):
            code[base + 4 * i] = word
        pc = base
        for _ in range(64):
            if pc not in code:
                return Trap(FETCH_FAULT, pc)
            insn = code[pc]
            if insn == 0x00100073 or insn & 0xffff == 0x9002:   # ebreak / c.ebreak
                return None
            self.next_pc = pc + (2 if insn & 3 != 3 else 4)
            self.pc = pc
            try:
                self.execute(insn if insn & 3 == 3 else insn & 0xffff, 4 if insn & 3 == 3 else 2)
            except Trap as trap:
                return trap
            except DebugEntry:
                return Trap(BREAKPOINT, pc)   # triggers do not fire in Debug Mode
            pc = self.next_pc
        return Trap(FETCH_FAULT, pc)

    # pylint: disable=too-many-branches,too-many-statements
    def execute(self, insn, length):
        if length == 2:
            return self.compressed(insn)
        opcode, rd = insn & 0x7f, (insn >> 7) & 31
        f3, rs1, rs2, f7 = (insn >> 12) & 7, (insn >> 15) & 31, (insn >> 20) & 31, insn >> 25
        a, b = self.x[rs1], self.x[rs2]
        imm_i = sx(insn >> 20, 12)
        xl = self.xlen
        if opcode == 0x37:
            self.setx(rd, sx(insn & 0xfffff000, 32))
        elif opcode == 0x17:
            self.setx(rd, self.pc + sx(insn & 0xfffff000, 32))
        elif opcode == 0x6f:
            imm = sx(((insn >> 31) << 20) | (((insn >> 12) & 0xff) << 12) | (((insn >> 20) & 1) << 11)
                     | (((insn >> 21) & 0x3ff) << 1), 21)
            self.setx(rd, self.next_pc)
            self.next_pc = (self.pc + imm) & self.mask
        elif opcode == 0x67 and f3 == 0:
            target = (a + imm_i) & self.mask & ~1
            self.setx(rd, self.next_pc)
            self.next_pc = target
        elif opcode == 0x63:
            imm = sx(((insn >> 31) << 12) | (((insn >> 7) & 1) << 11) | (((insn >> 25) & 0x3f) << 5)
                     | (((insn >> 8) & 15) << 1), 13)
            sa, sb = sx(a, xl), sx(b, xl)
            taken = {0: a == b, 1: a != b, 4: sa < sb, 5: sa >= sb, 6: a < b, 7: a >= b}.get(f3)
            if taken is None:
                raise Trap(ILLEGAL, insn)
            if taken:
                self.next_pc = (self.pc + imm) & self.mask
        elif opcode == 0x03:
            size = {0: 1, 1: 2, 2: 4, 3: 8, 4: 1, 5: 2, 6: 4}.get(f3)
            if size is None or (size == 8 and xl == 32) or (f3 == 6 and xl == 32):
                raise Trap(ILLEGAL, insn)
            self.setx(rd, self.load((a + imm_i) & self.mask, size, signed=f3 < 4))
        elif opcode == 0x23:
            size = {0: 1, 1: 2, 2: 4, 3: 8}.get(f3)
            if size is None or (size == 8 and xl == 32):
                raise Trap(ILLEGAL, insn)
            imm = sx(((insn >> 25) << 5) | ((insn >> 7) & 31), 12)
            self.store((a + imm) & self.mask, size, b)
        elif opcode in (0x13, 0x1b, 0x33, 0x3b):
            word = opcode in (0x1b, 0x3b)
            if word and xl == 32:
                raise Trap(ILLEGAL, insn)
            reg = opcode in (0x33, 0x3b)
            bits = 32 if word else xl
            lhs = a & ((1 << bits) - 1)
            rhs = b if reg else imm_i
            if reg and f7 == 1:
                value = self._muldiv(f3, lhs, rhs & ((1 << bits) - 1), bits, insn)
            else:
                shamt = (rhs & (bits - 1))
                if f3 == 0:
                    value = lhs - rhs if reg and f7 == 0x20 else lhs + rhs
                elif f3 == 1:
                    value = lhs << shamt
                elif f3 == 2:
                    value = int(sx(a, xl) < sx(rhs, xl))
                elif f3 == 3:
                    value = int(a < (rhs & self.mask))
                elif f3 == 4:
                    value = lhs ^ rhs
                elif f3 == 5:
                    arith = (insn >> 30) & 1
                    value = (sx(lhs, bits) >> shamt) if arith else (lhs >> shamt)
                elif f3 == 6:
                    value = lhs | rhs
                else:
                    value = lhs & rhs
                if word and f3 not in (0, 1, 5):
                    raise Trap(ILLEGAL, insn)
            value &= (1 << bits) - 1
            self.setx(rd, sx(value, bits) if word else value)
        elif opcode == 0x0f:
            pass   # fence, fence.i
        elif opcode == 0x73:
            self.system(insn, f3, rd, rs1, a)
        else:
            raise Trap(ILLEGAL, insn)
        return None

    def _muldiv(self, f3, a, b, bits, insn):
        sa, sb = sx(a, bits), sx(b, bits)
        mask = (1 << bits) - 1
        if f3 == 0:
            return a * b
        if f3 == 1:
            return (sa * sb) >> bits
        if f3 == 2:
            return (sa * b) >> bits
        if f3 == 3:
            return (a * b) >> bits
        if f3 == 4:
            return mask if b == 0 else (sa if sa == -(1 << (bits - 1)) and sb == -1 else int(sa / sb))
        if f3 == 5:
            return mask if b == 0 else a // b
        if f3 == 6:
            return sa if b == 0 else (0 if sb == -1 else sa - sb * int(sa / sb))
        return a if b == 0 else a % b

    def system(self, insn, f3, rd, rs1, a):
        if f3 == 0:
            if insn == 0x00000073:
                raise Trap(ECALL[self.mode])
            if insn == 0x00100073:
                self.ebreak()
            elif insn == 0x30200073 and self.mode == M:
                status = self.csr[MSTATUS]
                mpp = (status >> 11) & 3
                mpie = (status >> 7) & 1
                status = (status & ~((1 << 3) | (3 << 11))) | (mpie << 3) | (1 << 7)
                if mpp != M:
                    status &= ~(1 << 17)
                lowest = min(self._modes_int())
                self.csr[MSTATUS] = status | (lowest << 11)
                self.mode = mpp
                self.triggers.on_mret()
                self.next_pc = self.csr[MEPC]
            elif insn == 0x10500073:
                pass   # wfi completes at once
            else:
                raise Trap(ILLEGAL, insn)   # includes dret outside Debug Mode
            return
        address = insn >> 20
        imm = rs1
        source = a if f3 < 4 else imm
        op = f3 & 3
        if op == 0:
            raise Trap(ILLEGAL, insn)
        write = op == 1 or rs1 != 0
        old = self.read_csr(address) if (op != 1 or rd) else 0
        if write:
            value = source if op == 1 else (old | source if op == 2 else old & ~source)
            self.write_csr(address, value)
        self.setx(rd, old)

    def ebreak(self):
        enable = {M: 15, S: 13, U: 12}[self.mode]
        if (self.dcsr >> enable) & 1:
            raise DebugEntry(CAUSE_EBREAK, self.pc)
        raise Trap(BREAKPOINT, self.pc)

    def compressed(self, insn):
        op, f3 = insn & 3, insn >> 13
        rd = (insn >> 7) & 31
        if insn == 0x9002:
            return self.ebreak()
        if insn == 0x0001:
            return None
        if op == 1 and f3 == 0:   # c.addi
            imm = sx(((insn >> 12) & 1) << 5 | ((insn >> 2) & 31), 6)
            self.setx(rd, self.x[rd] + imm)
        elif op == 1 and f3 == 2:   # c.li
            self.setx(rd, sx(((insn >> 12) & 1) << 5 | ((insn >> 2) & 31), 6))
        elif op == 1 and f3 == 5:   # c.j
            bits = insn >> 2
            imm = (((bits >> 10) & 1) << 11 | ((bits >> 9) & 1) << 4 | ((bits >> 7) & 3) << 8
                   | ((bits >> 6) & 1) << 10 | ((bits >> 5) & 1) << 6 | ((bits >> 4) & 1) << 7
                   | ((bits >> 1) & 7) << 1 | (bits & 1) << 5)
            self.next_pc = (self.pc + sx(imm, 12)) & self.mask
        else:
            raise Trap(ILLEGAL, insn)
        return None


# -- a tiny assembler for campaign code ------------------------------------------
def _i(op, rd, f3, rs1, imm):
    return ((imm & 0xfff) << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | op


def _s(op, f3, rs1, rs2, imm):
    return (((imm >> 5) & 0x7f) << 25) | (rs2 << 20) | (rs1 << 15) | (f3 << 12) | ((imm & 31) << 7) | op


class Asm:
    """Encoders for the few instructions the campaigns write into scratch memory."""
    EBREAK, ECALL, MRET, DRET, NOP, FENCE_I, WFI = 0x00100073, 0x73, 0x30200073, 0x7b200073, 0x13, 0x100f, 0x10500073

    @staticmethod
    def addi(rd, rs1, imm):
        return _i(0x13, rd, 0, rs1, imm)

    @staticmethod
    def lui(rd, imm20):
        return ((imm20 & 0xfffff) << 12) | (rd << 7) | 0x37

    @staticmethod
    def auipc(rd, imm20):
        return ((imm20 & 0xfffff) << 12) | (rd << 7) | 0x17

    @staticmethod
    def ld(rd, rs1, imm=0):
        return _i(0x03, rd, 3, rs1, imm)

    @staticmethod
    def lw(rd, rs1, imm=0):
        return _i(0x03, rd, 2, rs1, imm)

    @staticmethod
    def sd(rs2, rs1, imm=0):
        return _s(0x23, 3, rs1, rs2, imm)

    @staticmethod
    def sw(rs2, rs1, imm=0):
        return _s(0x23, 2, rs1, rs2, imm)

    @staticmethod
    def sh(rs2, rs1, imm=0):
        return _s(0x23, 1, rs1, rs2, imm)

    @staticmethod
    def sb(rs2, rs1, imm=0):
        return _s(0x23, 0, rs1, rs2, imm)

    @staticmethod
    def csrrw(rd, csr, rs1):
        return _i(0x73, rd, 1, rs1, csr)

    @staticmethod
    def csrrs(rd, csr, rs1):
        return _i(0x73, rd, 2, rs1, csr)

    @staticmethod
    def jal(rd, offset):
        o = offset & 0x1fffff
        return (((o >> 20) & 1) << 31) | (((o >> 1) & 0x3ff) << 21) | (((o >> 11) & 1) << 20) \
            | (((o >> 12) & 0xff) << 12) | (rd << 7) | 0x6f

    @staticmethod
    def branch(f3, rs1, rs2, offset):
        o = offset & 0x1fff
        return (((o >> 12) & 1) << 31) | (((o >> 5) & 0x3f) << 25) | (rs2 << 20) | (rs1 << 15) \
            | (f3 << 12) | (((o >> 1) & 15) << 8) | (((o >> 11) & 1) << 7) | 0x63

    @staticmethod
    def beq(rs1, rs2, offset):
        return Asm.branch(0, rs1, rs2, offset)

    @staticmethod
    def bne(rs1, rs2, offset):
        return Asm.branch(1, rs1, rs2, offset)

    @staticmethod
    def j(offset):
        return Asm.jal(0, offset)

    @staticmethod
    def words(*words):
        return b''.join(w.to_bytes(4, 'little') for w in words)
