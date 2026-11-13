"""Project-derived instruction injection for pinned riscv-dv payloads.

The pinned pygen has no usable illegal-instruction or CSR stream in bare
program mode. These classes insert seeded instructions into its main program.
Every choice comes from the project target profile (ISA and CSR selection),
never from a core name. The inserted list is recorded for replay and triage.
"""
import random
import re

# Major opcodes defined by each declared base or extension group.
BASE = {0x03, 0x0f, 0x13, 0x17, 0x23, 0x33, 0x37, 0x63, 0x67, 0x6f, 0x73}
GROUPS = {'a': {0x2f}, 'f': {0x07, 0x27, 0x43, 0x47, 0x4b, 0x4f, 0x53},
          'd': {0x07, 0x27, 0x43, 0x47, 0x4b, 0x4f, 0x53}, 'v': {0x57}}
RV64 = {0x1b, 0x3b}
CSR_OPS = ('csrrw', 'csrrs', 'csrrc', 'csrrwi', 'csrrsi', 'csrrci')
TRAP_MARK = '.set RVW_TRAP_SKIP, 1\n'


def legal_opcodes(isa, xlen):
    base = isa.lower().split('_')[0][4:]
    legal = set(BASE)
    for letter, group in GROUPS.items():
        if letter in base or (letter in 'fd' and 'g' in base):
            legal |= group
    if xlen == 64:
        legal |= RV64
    return legal


def illegal_words(isa, xlen, rng):
    """One seeded 32-bit encoding that the declared ISA leaves undefined."""
    extra = [z for z in isa.lower().split('_')[1:] if z not in ('zicsr', 'zifencei')]
    legal = legal_opcodes(isa, xlen)
    # 32-bit length encodings: bits[1:0] == 3 and bits[4:2] != 7.
    opcodes = [op for op in range(128) if op & 3 == 3 and (op >> 2) & 7 != 7 and op not in legal]
    kinds = ['opcode', 'zero', 'load_funct3', 'store_funct3', 'branch_funct3', 'jalr_funct3']
    if not extra:
        # Bit-manipulation and other extensions reuse OP funct7 values.
        kinds += ['op_funct7', 'shift_funct7']
    kind = rng.choice(kinds)
    rest = rng.getrandbits(25) << 7
    def with_funct3(op, funct3):
        return (rest & ~(7 << 12)) | (funct3 << 12) | op
    if kind == 'opcode':
        word = rest | rng.choice(opcodes)
    elif kind == 'zero':
        word = 0
    elif kind == 'load_funct3':
        word = with_funct3(0x03, rng.choice([3, 6, 7] if xlen == 32 else [7]))
    elif kind == 'store_funct3':
        word = with_funct3(0x23, rng.choice([3, 4, 5, 6, 7] if xlen == 32 else [4, 5, 6, 7]))
    elif kind == 'branch_funct3':
        word = with_funct3(0x63, rng.choice([2, 3]))
    elif kind == 'jalr_funct3':
        word = with_funct3(0x67, rng.randrange(1, 8))
    elif kind == 'op_funct7':
        allowed = {0x00, 0x20} | ({0x01} if 'm' in isa.lower().split('_')[0][4:] else set())
        funct7 = rng.choice([f for f in range(128) if f not in allowed])
        word = ((rest & ~(0x7f << 25)) | (funct7 << 25)) | 0x33
    else:
        # SLLI needs funct7/funct6 zero; SRLI/SRAI allow only 0x00 and 0x20.
        funct3 = rng.choice([1, 5])
        shamt_bits = 5 if xlen == 32 else 6
        top = rng.choice([t for t in range(1 << (12 - shamt_bits))
                          if t not in ((0,) if funct3 == 1 else (0, 0x20 >> (shamt_bits - 5)))])
        word = (with_funct3(0x13, funct3) & ~(0xfff << 20)) | (top << (20 + shamt_bits)) \
            | (rng.getrandbits(shamt_bits) << 20)
    return word & 0xffffffff, kind


def main_region(lines):
    start = next((i for i, line in enumerate(lines) if line.startswith('main:')), None)
    end = next((i for i, line in enumerate(lines) if re.match(r'\s+la x\d+, test_done$', line)), None)
    if start is None or end is None or end <= start:
        raise ValueError('generated program has no main region')
    return start, end


def inject(text, target, test_class, seed, count):
    """Return (new text, inserted records) for the trap or CSR class."""
    rng = random.Random(f'rvw-inject-{test_class}-{seed}')
    lines = text.splitlines(keepends=True)
    start, end = main_region(lines)
    # Insert before an existing instruction so labels keep their targets.
    slots = sorted(rng.choices(range(start + 1, end), k=count))
    records, inserted = [], []
    if test_class == 'traps':
        for slot in slots:
            word, kind = illegal_words(target['isa'], target['xlen'], rng)
            records.append(dict(kind=kind, word=f'0x{word:08x}'))
            inserted.append((slot, f'                  .4byte 0x{word:08x} # rvw illegal {kind}\n'))
    elif test_class == 'csr':
        csrs = [r for r in target['csrs'] if r.get('present', True) and r.get('assembly_safe')]
        if not csrs:
            raise ValueError('CSR class needs an assembly-safe CSR in the project selection')
        for slot in slots:
            row, op = rng.choice(csrs), rng.choice(CSR_OPS)
            rd = rng.randrange(32)
            src = str(rng.randrange(32)) if op.endswith('i') else f'x{rng.randrange(32)}'
            records.append(dict(csr=row['name'], op=op))
            inserted.append((slot, f"                  {op} x{rd}, 0x{row['address']:03x}, {src} # rvw csr {row['name']}\n"))
    else:
        raise ValueError('no injection for class '+test_class)
    for slot, line in reversed(inserted):
        lines.insert(slot, line)
    body = ''.join(lines)
    if test_class == 'traps':
        body = TRAP_MARK + body
    return body, records
