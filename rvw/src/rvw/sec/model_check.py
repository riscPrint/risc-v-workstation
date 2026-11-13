"""Model-level leakage pre-check on the trace-driven OoO timing model.

The same contract pairs as `sec contract`, without RTL. Each secret's program runs on
Spike; its C2 trace drives `rvw ooo`. A planned microarchitecture states operand-dependent
latency rules per class (for example an early-terminating divider). The rules read the
operands from the reference trace. Different predicted timing with equal architectural
contract traces is a predicted leak. The prediction is model evidence, not RTL evidence.
"""
import copy
import json
from pathlib import Path
from rvw.cosim.trace import Trace
from .common import publish
from .pairs import CONTRACTS, projection
from . import core_adapter, rtl

RULES = ('fixed', 'quotient_bits', 'early_out')


def latency(rule, row, mnemonic):
    kind = rule.get('rule')
    a, b = row.get('rs1_rdata', 0), row.get('rs2_rdata', 0)
    if kind == 'fixed':
        return int(rule['latency'])
    if kind == 'quotient_bits':
        # A divider that skips leading zero quotient bits.
        if mnemonic in ('div', 'rem', 'divw', 'remw'):
            a, b = (abs(x - (1 << 32)) if x >> 31 else x for x in (a, b))
        q = a // b if b else 0
        return int(rule['base']) + int(rule.get('per_bit', 1)) * max(1, q.bit_length())
    if kind == 'early_out':
        # A multiplier that finishes early when the chosen operand is narrow.
        v = row.get(rule.get('operand', 'rs2') + '_rdata', 0)
        return int(rule['short']) if v.bit_length() <= int(rule['width']) else int(rule['long'])
    raise ValueError(f'unknown latency rule {kind}; choose from {", ".join(RULES)}')


def trace_ops(path, rules):
    """OoO instructions from a reference C2 trace, with rule latencies as custom classes."""
    from rvw.ooo.core import _instructions
    data = Path(path).read_bytes()
    ops = _instructions(data)
    reader = Trace(path)
    try:
        rows = [r for r in reader if 'event' not in r]
    finally:
        reader.file.close()
    if len(rows) != len(ops):
        raise ValueError('reference trace and model instructions differ in length')
    from dataclasses import replace
    needed = {}
    for i, (op, row) in enumerate(zip(ops, rows)):
        if op.kind in rules:
            n = latency(rules[op.kind], row, op.mnemonic)
            ops[i] = replace(op, kind=f'custom_{op.kind}_{n}')
            needed[ops[i].kind] = n
    return ops, rows, needed


def predict(description, ops, needed, max_cycles):
    from rvw.ooo.project import configuration
    from rvw.ooo.core import simulate
    d = copy.deepcopy(description)
    table = d['ooo'] if 'ooo' in d else d
    table['latencies'].update(needed)
    result = simulate(ops, configuration(d), max_cycles, backend='python')
    return result['cycles'], result.get('events', {})


def run(manifest, out):
    manifest = Path(manifest).resolve()
    plan = json.loads(manifest.read_text())
    out = Path(out).resolve(); out.mkdir(parents=True, exist_ok=False)
    if plan.get('contract') not in CONTRACTS:
        raise ValueError('declare an architectural leakage contract')
    secrets = plan['secrets']
    if len(secrets) != 2 or secrets[0] == secrets[1]:
        raise ValueError('two different secrets required')
    where = lambda p: (manifest.parent/p).resolve()
    binding = rtl.load(where(plan['binding']), rtl_required=False)
    description = json.loads(where(plan['model']).read_text())
    rules = plan.get('operand_latency', {})
    for k, r in rules.items():
        if r.get('rule') not in RULES:
            raise ValueError(f'unknown latency rule for {k}')
    cases = []
    for label, secret in zip('ab', secrets):
        folder = out/label; folder.mkdir()
        request = dict(program=plan['program'], secret=secret, public=plan.get('public', {}))
        (folder/'case.S').write_text(core_adapter.render(where(plan['template']), request))
        elf = core_adapter.compile_elf(folder/'case.S', folder, binding)
        ref = core_adapter.reference(elf, folder, binding)
        ops, rows, needed = trace_ops(ref, rules)
        cycles, events = predict(description, ops, needed, plan.get('max_cycles', 1_000_000))
        cases.append(dict(secret=secret, rows=rows, cycles=cycles,
                          latencies={k: v for k, v in sorted(needed.items())}, instructions=len(ops)))
    clauses = plan.get('clauses', ['pc', 'memory', 'branch'])
    if projection(cases[0]['rows'], clauses) != projection(cases[1]['rows'], clauses):
        comparison = dict(status='ineligible', channels=[])
    else:
        differ = cases[0]['cycles'] != cases[1]['cycles']
        comparison = dict(status='violation' if differ else 'no_leak_observed',
                          channels=['predicted_cycles'] if differ else [])
    summary = [dict(secret=c['secret'], predicted_cycles=c['cycles'], rule_latencies=c['latencies'],
                    instructions=c['instructions']) for c in cases]
    findings = [dict(program=plan['program'], cases=summary)] if comparison['status'] == 'violation' else []
    return publish(out, 'model-precheck', findings, comparison['status'] != 'ineligible', comparison=comparison,
                   cases=summary, model=str(where(plan['model'])), operand_latency=rules,
                   planned=plan.get('planned', ''),
                   evidence='trace-driven model prediction from Spike traces; not RTL evidence')
