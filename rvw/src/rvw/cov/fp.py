"""Scalar F/D/C operand-class coverage from validated C2 state records.

Register inputs are taken before retirement. Sticky fflags cannot identify all
flags raised by one operation. Such operations earn no raised-flag cross hit.
"""
from collections import Counter
from functools import lru_cache
from rvw.common.riscv import decode
from rvw.cosim.extensions import has_extension
from rvw.cov import captured

CLASSES = ('zero', 'subnormal', 'normal', 'infinity', 'qnan', 'snan')
ROUNDING = ('rne', 'rtz', 'rdn', 'rup', 'rmm')
ROUNDED = ('fadd', 'fsub', 'fmul', 'fdiv', 'fsqrt', 'fmadd', 'fmsub', 'fnmadd', 'fnmsub', 'fcvt')


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


def format_width(name):
    parts = name.split('.')
    for part in parts[1:]:
        if part in ('s', 'w'):
            # fcvt.w.d has a double source, not a single result.
            if part == 'w' and name.startswith('fcvt.'):
                continue
            return 32
        if part == 'd':
            return 64
    return 64 if 'fld' in name or 'fsd' in name else 32


def _is_fp(d):
    return d.cls == 'float' or d.dest_bank == 'f' or any(bank == 'f' for bank, _ in d.sources)


def _fp_extension(isa, letter):
    return has_extension(isa,letter) or has_extension(isa,'g')


def _allowed(name, isa):
    if isa is None:
        return True
    if not _fp_extension(isa, 'f'):
        return False
    if ('.d' in name or 'fld' in name or 'fsd' in name) and not _fp_extension(isa, 'd'):
        return False
    if name.startswith('c.'):
        required = 'zcd' if ('fld' in name or 'fsd' in name) else 'zcf'
        return has_extension(isa, 'c') or required in isa.lower().split('_')
    return True


@lru_cache(maxsize=8)
def encodings(xlen=64, isa=None):
    """Enumerate legal scalar encodings with the shared decoder."""
    words = [(f7 << 25) | (rs2 << 20) | (1 << 15) | (rm << 12) | (3 << 7) | 0x53
             for f7 in range(128) for rs2 in range(4) for rm in range(8)]
    words += [(4 << 27) | (fmt << 25) | (2 << 20) | (1 << 15) | (3 << 7) | op
              for fmt in (0, 1) for op in (0x43, 0x47, 0x4b, 0x4f)]
    words += [(f3 << 12) | (1 << 15) | (3 << 7) | op for f3 in (2, 3) for op in (7, 0x27)]
    words += [(f3 << 13) | (1 << 7) | (1 << 2) for f3 in (1, 3, 5, 7)]
    words += [(f3 << 13) | ((9 << 7) if f3 < 4 else (9 << 2)) | 2 for f3 in (1, 3, 5, 7)]
    result = {}
    for word in words:
        d = decode(word, xlen)
        if _is_fp(d) and _allowed(d.mnemonic, isa):
            result.setdefault(d.mnemonic, word)
    return result



@lru_cache(maxsize=8)
def catalog(xlen=64, isa=None):
    return {name: decode(word, xlen) for name, word in encodings(xlen, isa).items()}


def _slots(d):
    slots = [(pos, reg) for pos, reg in enumerate((d.rs1, d.rs2, d.rs3), 1)
             if reg is not None and reg[0] == 'f']
    if slots:
        return slots
    # Loads classify the loaded FP bits. Integer-to-FP conversions have no FP input.
    return [(1, None)] if d.cls == 'load' else [(0, None)]


def _domain(width, xlen, isa):
    return [(name, rm, slot, cls, flags)
            for name, d in catalog(xlen, isa).items() if format_width(name) == width
            for rm in ROUNDING for slot, _ in _slots(d)
            for cls in (('not_fp',) if slot == 0 else CLASSES) for flags in range(32)]


def report(records, width, *, xlen=64, flen=None, isa=None, include_holes=True):
    """Report per-source crosses; each call starts with unknown register state."""
    if width not in (32, 64) or xlen not in (32, 64):
        raise ValueError('FP width and XLEN must be 32 or 64')
    flen = flen or (64 if isa is None or _fp_extension(isa, 'd') else 32)
    registers, hits = {}, Counter()
    previous_fcsr = None
    observed = unknown = sticky_flags = 0
    integer = lambda value: int(value, 0) if isinstance(value, str) else value
    for row in records:
        if 'event' in row:
            continue
        insn = integer(row['insn'])
        d = decode(insn, xlen)
        name = d.mnemonic
        fcsr = integer(row['fcsr']) if 'fcsr' in row else None
        if _is_fp(d) and _allowed(name, isa) and format_width(name) == width and not row.get('trap'):
            rounded = name.startswith(ROUNDED)
            rm = ((insn >> 12) & 7) if rounded else 7
            if rm == 7:
                rm = (previous_fcsr >> 5) & 7 if previous_fcsr is not None else 7
            classes = []
            for position, reg in _slots(d):
                if position == 0:
                    classes.append((position, 'not_fp'))
                    continue
                if reg is None:
                    value = integer(row['fd_wdata']) if row.get('fd_valid') else None
                else:
                    value = registers.get(reg[1])
                if value is None:
                    break
                source_width = 64 if name == 'fcvt.s.d' else 32 if name == 'fcvt.d.s' else width
                raw_transfer = name.startswith(('fmv.', 'fsw', 'fsd', 'c.fs')) or d.cls == 'load'
                if source_width == 32 and flen == 64 and not raw_transfer and value >> 32 != 0xffffffff:
                    value = 0x7fc00000
                classes.append((position, operand_class(value, source_width)))
            if len(classes) != len(_slots(d)) or rm >= 5 or fcsr is None:
                unknown += 1
            elif previous_fcsr is None or previous_fcsr & 31:
                sticky_flags += 1
            else:
                flags = fcsr & 31
                observed += 1
                for position, cls in classes:
                    hits[(name, ROUNDING[rm], position, cls, flags)] += 1
        if row.get('fd_valid'):
            registers[integer(row['fd'])] = integer(row['fd_wdata'])
        previous_fcsr = fcsr
    domain = _domain(width, xlen, isa)
    result = dict(schema='rvw.fp-coverage/2', width=width, xlen=xlen, isa=isa, flen=flen,
                  observed=observed, unknown_operands_or_rm=unknown, unknown_raised_flags=sticky_flags,
                  bins=len(domain), hit_bins=len(hits),
                  hits=[dict(bin=list(key), count=count) for key, count in sorted(hits.items())],
                  limits=['Per-source operand classes; not a full tuple cross of all operands.',
                          'Unrounded instructions use the preceding frm as context.',
                          'Integer-to-FP input class is not_fp; loads classify loaded bits.',
                          'All flag masks are enumerated; unreachable bins are not waived.',
                          'C2 state must match the reference before closure claims.'])
    _class_projection(result, domain, hits, include_holes)
    if include_holes:
        result['holes'] = [list(key) for key in domain if key not in hits]
    return result


def _class_projection(result, domain, hits, include_holes=True):
    classes = set(key[:-1] for key in domain)
    covered = set(key[:-1] for key in hits)
    result['operand_class_bins'] = len(classes)
    result['hit_operand_class_bins'] = len(covered)
    if include_holes:
        result['operand_class_holes'] = [list(key) for key in sorted(classes - covered)]


def merge(reports):
    """Union independent traces without carrying their register states across runs."""
    reports = list(reports)
    if not reports:
        raise ValueError('at least one coverage report required')
    result = dict(reports[0])
    identity = ('schema', 'width', 'xlen', 'isa', 'flen', 'bins')
    hits = Counter()
    for report_ in reports:
        if any(report_[key] != result[key] for key in identity):
            raise ValueError('FP coverage profiles differ')
        for hit in report_['hits']:
            hits[tuple(hit['bin'])] += hit['count']
    for key in ('observed', 'unknown_operands_or_rm', 'unknown_raised_flags'):
        result[key] = sum(r[key] for r in reports)
    result.update(traces=sum(r.get('traces',1) for r in reports), hit_bins=len(hits),
                  hits=[dict(bin=list(key), count=count) for key, count in sorted(hits.items())],
                  holes=[list(key) for key in _domain(result['width'], result['xlen'], result['isa']) if key not in hits])
    _class_projection(result, _domain(result['width'], result['xlen'], result['isa']), hits)
    return result


@captured.command
def report_traces(paths, width):
    """Credit complete C1-bound DUT traces. Bin hits do not prove arithmetic."""
    from rvw.cosim.trace import Trace
    from rvw.cov.functional import qualification
    reports=[]
    for path in paths:
        item=captured.file(path)
        reader=Trace(item.copy)
        try:
            header=reader.header
            if header['schema']!='rvw.rvfi/2' or not reader.state:
                raise ValueError('FP coverage requires C2/2 state')
            if header.get('config')=='reference':
                raise ValueError('reference-only execution earns no DUT coverage')
            if not any(format_width(name)==width for name in catalog(header['xlen'],header['isa'])):
                raise ValueError('selected FP format is absent from the trace ISA')
            evidence=qualification(item)
            if not evidence['qualified']:
                raise ValueError('FP coverage requires a conclusive C1 pass: '+evidence['reason'])
            reports.append(report(reader,width,xlen=header['xlen'],isa=header['isa'],include_holes=False))
        finally:
            reader.close()
    result=merge(reports)
    result['qualification_policy']='c1-pass-complete-c2-v1'
    result['limits'].append('C1 qualification establishes execution. Compare against the reference before correctness or closure claims.')
    return result
