"""FP operand classes and observed cross bins from C2/2 retirement records.

Accrued flags do not identify flags raised by one operation. Only a preceding
zero fflags state makes the operation's raised flags observable.
"""
from collections import Counter

CLASSES = ('zero', 'subnormal', 'normal', 'infinity', 'qnan', 'snan')
ROUNDING = ('rne', 'rtz', 'rdn', 'rup', 'rmm')


def operand_class(bits, width):
    if width not in (32, 64):
        raise ValueError('FP width must be 32 or 64')
    fraction_bits, exponent_bits = (23, 8) if width == 32 else (52, 11)
    fraction = bits & ((1 << fraction_bits) - 1)
    exponent = (bits >> fraction_bits) & ((1 << exponent_bits) - 1)
    if exponent == 0:
        return 'subnormal' if fraction else 'zero'
    if exponent == (1 << exponent_bits) - 1:
        return ('qnan' if fraction & (1 << (fraction_bits - 1)) else 'snan') if fraction else 'infinity'
    return 'normal'


# Rounded arithmetic. Other FP instructions need their own source and RM rules.
OPS = {0: 'fadd', 4: 'fsub', 8: 'fmul', 12: 'fdiv', 44: 'fsqrt'}


def report(records, width):
    """Report holes in per-source class bins. Unknown inputs get no hit."""
    registers = {}
    hits = Counter()
    previous_fcsr = None
    observed = unknown = sticky_flags = 0
    for row in records:
        if 'event' in row:
            continue
        insn = int(row['insn'], 0) if isinstance(row['insn'], str) else row['insn']
        integer = lambda k: int(row[k], 0) if isinstance(row[k], str) else row[k]
        fcsr = integer('fcsr') if 'fcsr' in row else None
        op = OPS.get((insn >> 25) & ~1) if insn & 127 == 0x53 else None
        instruction_width = 64 if (insn >> 25) & 1 else 32
        if op and instruction_width == width:
            rm = (insn >> 12) & 7
            if rm == 7:
                rm = (previous_fcsr >> 5) if previous_fcsr is not None else 7
            sources = [(insn >> 15) & 31]
            if op != 'fsqrt':
                sources.append((insn >> 20) & 31)
            if rm >= 5 or fcsr is None or any(src not in registers for src in sources):
                unknown += 1
            elif previous_fcsr is None or previous_fcsr & 31:
                sticky_flags += 1
            else:
                observed += 1
                for index, src in enumerate(sources):
                    value = registers[src]
                    # A malformed box is consumed as canonical single-precision NaN.
                    if width == 32 and value >> 32 != 0xffffffff:
                        value = 0x7fc00000
                    hits[(op, ROUNDING[rm], index + 1, operand_class(value, width), fcsr & 31)] += 1
        if row.get('fd_valid'):
            registers[row['fd']] = integer('fd_wdata')
        previous_fcsr = fcsr
    domains = [(op, rm, src, cls, flags) for op in OPS.values() for rm in ROUNDING
               for src in range(1, 2 if op == 'fsqrt' else 3) for cls in CLASSES for flags in range(32)]
    return dict(schema='rvw.fp-coverage/1', width=width, observed=observed,
                unknown_operands_or_rm=unknown, unknown_raised_flags=sticky_flags,
                bins=len(domains), hit_bins=len(hits),
                holes=[list(key) for key in domains if key not in hits],
                hits=[dict(bin=list(key), count=count) for key, count in sorted(hits.items())],
                limits=['Rounded add/sub/mul/div/sqrt only; per-source classes, not operand tuple crosses.',
                        'All flag masks are enumerated; unreachable bins are not waived.',
                        'C2 state must be validated against the reference before closure claims.'])
