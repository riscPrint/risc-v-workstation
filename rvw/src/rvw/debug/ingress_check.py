"""Check a core's trace encoder ingress, sampled from RTL, against C2 (#168, #194).

The simulator samples project-declared ingress signals into `te_ingress.csv` (RiscvSim
`--trace-ingress`). This module:

1. compares each RTL ingress row with the row derived from C2 retirement (`ingress_rows`);
2. N-Trace: rebuilds retirement from the RTL ingress and the ELF, encodes it with the rvw
   N-Trace codec, decodes the messages with the ELF and compares the PC flow with C2;
3. E-Trace (with `--reference`): encodes the RTL ingress with the pinned reference encoder,
   decodes the packets and compares the PC flow with C2.

The ingress is the encoder's input. A match shows the core's ingress port carries enough
information to trace this run. It is not evidence of a hardware encoder.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from rvw.common.riscv import decode as decode_instruction

from . import etrace, etrace_flow as ef, ntrace, ntrace_check

SCHEMA = 'rvw.trace-ingress-check/1'
INT_FIELDS = ('itype_0', 'cause', 'priv', 'context', 'ctype', 'iretire_0', 'ilastsize_0')


def read_ingress(path):
    """RTL ingress rows with integer fields (tval and iaddr_0 are hexadecimal in the CSV)."""
    with Path(path).open() as stream:
        rows = list(csv.DictReader(stream))
    out = []
    for number, row in enumerate(rows, 2):
        missing = set(etrace.INGRESS) - set(row)
        if missing:
            raise ValueError(f'{path}: line {number} lacks {", ".join(sorted(missing))}')
        try:
            entry = {k: int(row[k]) for k in INT_FIELDS}
            entry['tval'] = int(row['tval'], 16)
            entry['iaddr_0'] = int(row['iaddr_0'], 16)
        except ValueError as exc:
            raise ValueError(f'{path}: line {number}: {exc}') from None
        out.append(entry)
    return out


def _normal(entry):
    e = dict(entry)
    for key in ('tval', 'iaddr_0'):
        if isinstance(e[key], str):
            e[key] = int(e[key], 16)
    return {k: int(e[k]) for k in etrace.INGRESS}


def compare(actual, expected):
    a = [_normal(e) for e in actual]
    b = [_normal(e) for e in expected]
    for index, (x, y) in enumerate(zip(a, b)):
        if x != y:
            fields = sorted(k for k in x if x[k] != y[k])
            return {'status': 'mismatch', 'first_difference': index, 'fields': fields,
                    'actual': _hex(x), 'expected': _hex(y), 'actual_rows': len(a), 'expected_rows': len(b)}
    if len(a) != len(b):
        return {'status': 'mismatch', 'first_difference': min(len(a), len(b)),
                'actual_rows': len(a), 'expected_rows': len(b)}
    return {'status': 'match', 'rows': len(a)} if a else {'status': 'inconclusive', 'reason': 'no ingress rows'}


def _hex(entry):
    return {k: (hex(v) if k in ('tval', 'iaddr_0') else v) for k, v in entry.items()}


def retirement(entries, code, *, xlen):
    """C2-like retirement rows (pc, insn, pc_next, mode, trap, exc, irq) from ingress and code.
    `pc_next` is the address of the next ingress row; the last row falls through."""
    rows, pending_irq = [], None
    for index, entry in enumerate(entries):
        if entry['itype_0'] == ef.INTERRUPT:
            pending_irq = entry['cause']
            continue
        pc = _normal(entry)['iaddr_0']
        insn = code.insn(pc)
        length = decode_instruction(insn, xlen).length
        later = next((e for e in entries[index + 1:]), None)
        pc_next = _normal(later)['iaddr_0'] if later is not None else pc + length
        row = {'pc': pc, 'insn': insn, 'pc_next': pc_next, 'mode': entry['priv']}
        if entry['itype_0'] == ef.EXCEPTION:
            row.update(trap=True, exc=(entry['cause'], _normal(entry)['tval']))
        if pending_irq is not None:
            row['irq'] = pending_irq
            pending_irq = None
        rows.append(row)
    return rows


def check(ingress, rvfi, elf, *, ntrace_profile=None, reference=None, static_config=None, user_config=None,
          toolchain=None):
    with Path(rvfi).open() as stream:
        xlen = json.loads(stream.readline()).get('xlen', 64)
    code = ntrace.Code(ntrace_check._segments(elf, xlen))
    rows, complete, xlen = ef.retirement(rvfi, code=code)
    want_pcs = ef.expected_pcs(rows)
    actual = read_ingress(ingress)
    result = {'schema': SCHEMA, 'ingress_sha256': ef.sha256(Path(ingress).read_bytes()),
              'rvfi_sha256': ef.sha256(Path(rvfi).read_bytes()), 'complete': complete,
              'retired': len(want_pcs), 'ingress_rows': len(actual)}
    result['ingress'] = compare(actual, ef.ingress_rows(rows, xlen=xlen))
    result['rebuilt_trap_rows'] = sum(1 for r in rows if r.get('rebuilt'))
    try:
        rtl_rows = retirement(actual, code, xlen=xlen)
        params = ntrace.normalize(ntrace_profile)
        messages = ntrace.encode(rtl_rows, params, xlen=xlen)
        decoded = ntrace.decode(messages, code, params, xlen=xlen)
        report, _ = ef.windows([(pcs, clean) for pcs, clean, _ in decoded], want_pcs)
        flow = ef.verdict(report, want_pcs, complete=complete, gaps=False)
        result['ntrace'] = {'status': flow, 'mode': params['mode'], 'messages': len(messages), 'windows': report}
    except ValueError as exc:
        result['ntrace'] = {'status': 'mismatch', 'reason': str(exc)}
    if reference is not None:
        try:
            packets, _ = ef.encode(reference, actual_entries(actual), static_config, user_config)
            report, _, losses, skipped = ef.decode_stream(reference, packets, want_pcs, static_config, user_config,
                                                          toolchain=toolchain)
            result['etrace'] = {'status': ef.verdict(report, want_pcs, complete=complete, gaps=bool(losses)),
                                'decoder_rev': etrace.REFERENCE_REV, 'packets': len(packets), 'windows': report}
        except ValueError as exc:
            result['etrace'] = {'status': 'inconclusive', 'reason': str(exc)[-400:]}
    result['status'] = overall(result)
    return result


def actual_entries(actual):
    return [{**e, 'tval': f'{e["tval"]:x}', 'iaddr_0': f'{e["iaddr_0"]:x}'} for e in actual]


def overall(result):
    parts = [result['ingress']['status'], result['ntrace']['status']]
    if 'etrace' in result:
        parts.append(result['etrace']['status'])
    if 'mismatch' in parts:
        return 'mismatch'
    if not result['complete'] or any(p not in ('match', 'flow_match') for p in parts):
        return 'inconclusive'
    return 'match'
