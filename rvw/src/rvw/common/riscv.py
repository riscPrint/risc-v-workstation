"""One RISC-V instruction decoder for every rvw tool (coverage, failure bundles, cosim).

`decode(insn, xlen)` names an RV32/RV64 IMAFDC(+Zicsr, Zifencei, Zba, Zbb, Zbs) word and lists the
registers it reads, with their bank (`x` or `f`), and the bank of its destination. It is a
structural decoder for tooling: it does not compute immediates or execute anything (execution
semantics stay in Spike), and an encoding it does not know is reported as `unknown` with no
sources rather than guessed. Reserved fields make an encoding unknown (for example a reserved
FP rounding mode, rm 5 or 6).

    d = decode(0x02004033)          # Decoded(mnemonic='div', cls='divide', length=4, ...)
    d.sources                       # (('x', 0), ('x', 0))
    integer_sources(insn)           # (rs1, rs2) integer source indices, 0 when absent
    classify(insn)                  # coarse class: load, store, amo, fence, system, muldiv, fp,
                                    # branch, alu, unknown

Classes of `Decoded.cls`: alu, multiply, divide, load, store, branch, jump, csr, system, fence,
atomic, float, unknown.
"""
from __future__ import annotations

from dataclasses import dataclass


Reg = tuple[str, int]   # (bank, index), bank 'x' or 'f'


@dataclass(frozen=True)
class Decoded:
    mnemonic: str
    cls: str
    length: int
    # Source operands by position, as in the 32-bit form a compressed instruction expands to (the
    # positions RVFI reports): C.MV is `add rd, x0, rs2`, so rs1 is x0. None: no such operand.
    rs1: Reg | None
    rs2: Reg | None
    rs3: Reg | None
    # Bank of the destination register: 'f' when the instruction writes an FP register, else 'x'
    # (also for instructions without a destination; RVFI rd=0 marks those).
    dest_bank: str

    @property
    def sources(self) -> tuple[Reg, ...]:
        """Registers read, in operand order."""
        return tuple(r for r in (self.rs1, self.rs2, self.rs3) if r is not None)

    def as_dict(self) -> dict:
        """The form `rvw cov functional` records: mnemonic, class, uses, dest_bank, length."""
        return {"mnemonic": self.mnemonic, "class": self.cls, "uses": list(self.sources),
                "dest_bank": self.dest_bank, "length": self.length}


UNKNOWN2 = Decoded('unknown', 'unknown', 2, None, None, None, 'x')
UNKNOWN4 = Decoded('unknown', 'unknown', 4, None, None, None, 'x')


def _mk(m, cls, length, src, dest):
    slots = list(src) + [None] * (3 - len(src))
    return Decoded(m, cls, length, slots[0], slots[1], slots[2], dest)


def _x(*regs):
    return tuple(('x', r) for r in regs)


def _f(*regs):
    return tuple(('f', r) for r in regs)


def _compressed(insn: int, xlen: int) -> Decoded:
    q, f = insn & 3, (insn >> 13) & 7
    rd = (insn >> 7) & 31
    rs1c, rs2c = 8 + ((insn >> 7) & 7), 8 + ((insn >> 2) & 7)
    rs2 = (insn >> 2) & 31

    def d(m, cls, src=(), dest='x'):
        return _mk(m, cls, 2, src, dest)

    if q == 0:
        if f == 0:
            # nzuimm == 0 is reserved (0x0000 is the defined illegal instruction)
            return d('c.addi4spn', 'alu', _x(2)) if (insn >> 5) & 0xff else UNKNOWN2
        if f == 1:
            return d('c.fld', 'load', _x(rs1c), 'f')
        if f == 2:
            return d('c.lw', 'load', _x(rs1c))
        if f == 3:
            return d('c.ld', 'load', _x(rs1c)) if xlen == 64 else d('c.flw', 'load', _x(rs1c), 'f')
        if f == 5:
            return d('c.fsd', 'store', _x(rs1c) + _f(rs2c))
        if f == 6:
            return d('c.sw', 'store', _x(rs1c, rs2c))
        if f == 7:
            return d('c.sd', 'store', _x(rs1c, rs2c)) if xlen == 64 else d('c.fsw', 'store', _x(rs1c) + _f(rs2c))
        return UNKNOWN2
    if q == 1:
        imm6 = ((insn >> 7) & 0x20) | ((insn >> 2) & 0x1f)
        if f == 0:
            return d('c.nop' if rd == 0 else 'c.addi', 'alu', _x(rd))
        if f == 1:
            if xlen == 32:
                return d('c.jal', 'jump')
            return d('c.addiw', 'alu', _x(rd)) if rd else UNKNOWN2
        if f == 2:
            return d('c.li', 'alu', _x(0))
        if f == 3:
            if not imm6:
                return UNKNOWN2       # reserved
            return d('c.addi16sp', 'alu', _x(2)) if rd == 2 else d('c.lui', 'alu')
        if f == 4:
            sub = (insn >> 10) & 3
            if sub != 3:
                if sub < 2 and xlen == 32 and insn & 0x1000:
                    return UNKNOWN2    # shamt[5] is reserved on RV32; zero is a hint
                return d(('c.srli', 'c.srai', 'c.andi')[sub], 'alu', _x(rs1c))
            names = ('c.sub', 'c.xor', 'c.or', 'c.and') if not insn & 0x1000 else ('c.subw', 'c.addw', None, None)
            m = names[(insn >> 5) & 3]
            if m and m.endswith('w') and xlen == 32:
                m = None
            return d(m, 'alu', _x(rs1c, rs2c)) if m else UNKNOWN2
        if f == 5:
            return d('c.j', 'jump')
        return d('c.beqz' if f == 6 else 'c.bnez', 'branch', _x(rs1c, 0))
    if q == 2:
        if f == 0:
            if xlen == 32 and insn & 0x1000:
                return UNKNOWN2        # shamt[5] is reserved on RV32
            return d('c.slli', 'alu', _x(rd))
        if f == 1:
            return d('c.fldsp', 'load', _x(2), 'f')
        if f == 2:
            return d('c.lwsp', 'load', _x(2)) if rd else UNKNOWN2
        if f == 3:
            if xlen == 32:
                return d('c.flwsp', 'load', _x(2), 'f')
            return d('c.ldsp', 'load', _x(2)) if rd else UNKNOWN2
        if f == 4:
            if rs2:
                return d('c.add', 'alu', _x(rd, rs2)) if insn & 0x1000 else d('c.mv', 'alu', _x(0, rs2))
            if insn & 0x1000:
                return d('c.ebreak', 'system') if rd == 0 else d('c.jalr', 'jump', _x(rd))
            return d('c.jr', 'jump', _x(rd)) if rd else UNKNOWN2
        if f == 5:
            return d('c.fsdsp', 'store', _x(2) + _f(rs2))
        if f == 6:
            return d('c.swsp', 'store', _x(2, rs2))
        return d('c.sdsp', 'store', _x(2, rs2)) if xlen == 64 else d('c.fswsp', 'store', _x(2) + _f(rs2))
    return UNKNOWN2


_FMT = {0: '.s', 1: '.d'}


def _float(insn: int, xlen: int) -> Decoded:
    op, f3, f7 = insn & 127, (insn >> 12) & 7, insn >> 25
    rs1, rs2, rs3 = (insn >> 15) & 31, (insn >> 20) & 31, insn >> 27
    fmt = _FMT.get(f7 & 3)
    if fmt is None:
        return UNKNOWN4

    def d(m, src, dest='f'):
        return _mk(m, 'float', 4, src, dest)

    # Forms with a rounding-mode field (funct3 is rm): rm 5 and 6 are reserved encodings.
    # 7 (DYN) selects frm. This structural decoder cannot check that run-time CSR value.
    f5 = f7 >> 2
    if (op != 0x53 or f5 in (0, 1, 2, 3, 8, 11, 24, 26)) and f3 in (5, 6):
        return UNKNOWN4
    if op != 0x53:
        return d({0x43: 'fmadd', 0x47: 'fmsub', 0x4b: 'fnmsub', 0x4f: 'fnmadd'}[op] + fmt, _f(rs1, rs2, rs3))
    if f5 in (0, 1, 2, 3):
        return d(('fadd', 'fsub', 'fmul', 'fdiv')[f5] + fmt, _f(rs1, rs2))
    if f5 == 11 and rs2 == 0:
        return d('fsqrt' + fmt, _f(rs1))
    if f5 == 4 and f3 < 3:
        return d(('fsgnj', 'fsgnjn', 'fsgnjx')[f3] + fmt, _f(rs1, rs2))
    if f5 == 5 and f3 < 2:
        return d(('fmin', 'fmax')[f3] + fmt, _f(rs1, rs2))
    if f5 == 8 and rs2 in (0, 1) and rs2 != (f7 & 3):           # fcvt.s.d / fcvt.d.s
        return d(f'fcvt{fmt}{_FMT[rs2]}', _f(rs1))
    if f5 == 20 and f3 < 3:
        return d(('fle', 'flt', 'feq')[f3] + fmt, _f(rs1, rs2), 'x')
    ints = {0: 'w', 1: 'wu', 2: 'l', 3: 'lu'}
    if f5 == 24 and rs2 in ints and (rs2 < 2 or xlen == 64):
        return d(f'fcvt.{ints[rs2]}{fmt}', _f(rs1), 'x')
    if f5 == 26 and rs2 in ints and (rs2 < 2 or xlen == 64):
        return d(f'fcvt{fmt}.{ints[rs2]}', _x(rs1))
    if f5 == 28 and rs2 == 0 and f3 == 0 and (fmt == '.s' or xlen == 64):
        return d('fmv.x.w' if fmt == '.s' else 'fmv.x.d', _f(rs1), 'x')
    if f5 == 28 and rs2 == 0 and f3 == 1:
        return d('fclass' + fmt, _f(rs1), 'x')
    if f5 == 30 and rs2 == 0 and f3 == 0 and (fmt == '.s' or xlen == 64):
        return d('fmv.w.x' if fmt == '.s' else 'fmv.d.x', _x(rs1))
    return UNKNOWN4


def _bitmanip(insn, xlen):
    """Zba/Zbb/Zbs encodings, including RV32 shift and RV64 word restrictions."""
    op, f3, f7 = insn & 127, (insn >> 12) & 7, insn >> 25
    rs1, rs2 = (insn >> 15) & 31, (insn >> 20) & 31
    if op in (0x3b, 0x1b) and xlen != 64:
        return None
    name = None
    binary = False
    if op in (0x33, 0x3b):
        word = op == 0x3b
        if f7 == 0x04 and f3 == 4 and rs2 == 0 and word == (xlen == 64):
            name = 'zext.h'
        else:
            binary = True
            if f7 == 0x30:
                name = {1: 'rol', 5: 'ror'}.get(f3)
                if name and word:
                    name += 'w'
            elif f7 == 0x10:
                name = {2: 'sh1add', 4: 'sh2add', 6: 'sh3add'}.get(f3)
                if name and word:
                    name += '.uw'
            elif word:
                name = 'add.uw' if f7 == 0x04 and f3 == 0 else None
            elif f7 == 0x20:
                name = {4: 'xnor', 6: 'orn', 7: 'andn'}.get(f3)
            elif f7 == 0x05:
                name = {4: 'min', 5: 'minu', 6: 'max', 7: 'maxu'}.get(f3)
            else:
                name = {(0x14, 1): 'bset', (0x24, 1): 'bclr',
                        (0x24, 5): 'bext', (0x34, 1): 'binv'}.get((f7, f3))
    elif op in (0x13, 0x1b):
        word = op == 0x1b
        if f7 == 0x30 and f3 == 1:
            name = {0: 'clz', 1: 'ctz', 2: 'cpop'}.get(rs2)
            if name and word:
                name += 'w'
            elif not word and rs2 in (4, 5):
                name = 'sext.b' if rs2 == 4 else 'sext.h'
        elif not word and insn & 0xfff0707f == 0x28705013:
            name = 'orc.b'
        elif not word and insn & 0xfff0707f == (0x6b805013 if xlen == 64 else 0x69805013):
            name = 'rev8'
        elif word and insn & 0xfc00707f == 0x0800101b:
            name = 'slli.uw'  # 6-bit shift amount, even though the opcode is OP-IMM-32
        else:
            # RV32 and word rotates use a 5-bit amount. RV64 full-width forms use 6.
            mask = 0xfe00707f if word or xlen == 32 else 0xfc00707f
            names = {0x6000501b: 'roriw'} if word else {
                0x60005013: 'rori', 0x48001013: 'bclri', 0x48005013: 'bexti',
                0x68001013: 'binvi', 0x28001013: 'bseti'}
            name = names.get(insn & mask)
    if name:
        return _mk(name, 'alu', 4, _x(rs1, rs2) if binary else _x(rs1), 'x')
    return None


def decode(insn: int, xlen: int = 64) -> Decoded:
    """Decode an instruction word (16-bit when the low two bits are not 11)."""
    if insn & 3 != 3:
        return _compressed(insn & 0xffff, xlen)
    bitmanip = _bitmanip(insn, xlen)
    if bitmanip is not None:
        return bitmanip
    op, f3, f7 = insn & 127, (insn >> 12) & 7, insn >> 25
    rs1, rs2 = (insn >> 15) & 31, (insn >> 20) & 31

    def d(m, cls, src=(), dest='x'):
        return _mk(m, cls, 4, src, dest)

    if op in (0x33, 0x3b):
        w = 'w' if op == 0x3b else ''
        if w and xlen == 32:
            return UNKNOWN4
        if f7 == 1:
            if w and f3 in (1, 2, 3):
                return UNKNOWN4
            m = ('mul', 'mulh', 'mulhsu', 'mulhu', 'div', 'divu', 'rem', 'remu')[f3] + w
            return d(m, 'multiply' if f3 < 4 else 'divide', _x(rs1, rs2))
        if f7 == 0:
            m = ('add', 'sll', 'slt', 'sltu', 'xor', 'srl', 'or', 'and')[f3]
        elif f7 == 0x20:
            m = {0: 'sub', 5: 'sra'}.get(f3)
        else:
            m = None
        if m is None or (w and f3 not in (0, 1, 5)):
            return UNKNOWN4
        return d(m + w, 'alu', _x(rs1, rs2))
    if op in (0x13, 0x1b):
        w = op == 0x1b
        if w and xlen == 32:
            return UNKNOWN4
        m = ('addi', 'slli', 'slti', 'sltiu', 'xori', 'srli', 'ori', 'andi')[f3]
        if f3 == 5 and (insn >> 30) & 1:
            m = 'srai'
        if w:
            if f3 not in (0, 1, 5):
                return UNKNOWN4
            m += 'w'
        if f3 in (1, 5):
            upper = insn >> (25 if w or xlen == 32 else 26)
            allowed = (0, 0x20 if w or xlen == 32 else 0x10) if f3 == 5 else (0,)
            if upper not in allowed:
                return UNKNOWN4
        return d(m, 'alu', _x(rs1))
    if op in (0x37, 0x17):
        return d('lui' if op == 0x37 else 'auipc', 'alu')
    if op == 0x03:
        m = {0: 'lb', 1: 'lh', 2: 'lw', 3: 'ld', 4: 'lbu', 5: 'lhu', 6: 'lwu'}.get(f3)
        if m is None or (xlen == 32 and m in ('ld', 'lwu')):
            return UNKNOWN4
        return d(m, 'load', _x(rs1))
    if op == 0x07:
        m = {2: 'flw', 3: 'fld'}.get(f3)
        return d(m, 'load', _x(rs1), 'f') if m else UNKNOWN4
    if op == 0x23:
        m = {0: 'sb', 1: 'sh', 2: 'sw', 3: 'sd'}.get(f3)
        if m is None or (xlen == 32 and m == 'sd'):
            return UNKNOWN4
        return d(m, 'store', _x(rs1, rs2))
    if op == 0x27:
        m = {2: 'fsw', 3: 'fsd'}.get(f3)
        return d(m, 'store', _x(rs1) + _f(rs2)) if m else UNKNOWN4
    if op == 0x63:
        m = {0: 'beq', 1: 'bne', 4: 'blt', 5: 'bge', 6: 'bltu', 7: 'bgeu'}.get(f3)
        return d(m, 'branch', _x(rs1, rs2)) if m else UNKNOWN4
    if op == 0x6f:
        return d('jal', 'jump')
    if op == 0x67:
        return d('jalr', 'jump', _x(rs1)) if f3 == 0 else UNKNOWN4
    if op == 0x73:
        if f3:
            m = {1: 'csrrw', 2: 'csrrs', 3: 'csrrc', 5: 'csrrwi', 6: 'csrrsi', 7: 'csrrci'}.get(f3)
            return d(m, 'csr', _x(rs1) if f3 < 4 else ()) if m else UNKNOWN4
        if insn & 0xfe007fff == 0x12000073:
            return d('sfence.vma', 'system', _x(rs1, rs2))
        m = {0x00000073: 'ecall', 0x00100073: 'ebreak', 0x10200073: 'sret', 0x30200073: 'mret',
             0x10500073: 'wfi'}.get(insn)
        return d(m, 'system') if m else UNKNOWN4
    if op == 0x0f:
        m = {0: 'fence', 1: 'fence.i'}.get(f3)
        return d(m, 'fence') if m else UNKNOWN4
    if op == 0x2f:
        name = {0: 'amoadd', 1: 'amoswap', 2: 'lr', 3: 'sc', 4: 'amoxor', 8: 'amoor', 12: 'amoand',
                16: 'amomin', 20: 'amomax', 24: 'amominu', 28: 'amomaxu'}.get(insn >> 27)
        width = {2: '.w', 3: '.d'}.get(f3)
        if name is None or width is None or (width == '.d' and xlen == 32) or (name == 'lr' and rs2):
            return UNKNOWN4
        return d(name + width, 'atomic', _x(rs1) if name == 'lr' else _x(rs1, rs2))
    if op in (0x43, 0x47, 0x4b, 0x4f, 0x53):
        return _float(insn, xlen)
    return UNKNOWN4


def integer_sources(insn: int, xlen: int = 64) -> tuple[int, int]:
    """(rs1, rs2): the integer registers in the rs1 and rs2 operand positions (of the expanded form
    for compressed instructions), 0 when the position is absent or holds an FP register."""
    d = decode(insn, xlen)
    return tuple(r[1] if r is not None and r[0] == 'x' else 0 for r in (d.rs1, d.rs2))


_COARSE = {'multiply': 'muldiv', 'divide': 'muldiv', 'jump': 'branch', 'csr': 'system', 'atomic': 'amo',
           'float': 'fp'}


def classify(insn: int | None, xlen: int = 64) -> str:
    """Coarse class of an instruction word: load, store, amo, fence, system, muldiv, fp, branch
    (jumps included), alu, or unknown (also for None)."""
    if insn is None:
        return 'unknown'
    cls = decode(insn, xlen).cls
    return _COARSE.get(cls, cls)
