"""Bounded Z3 instruction candidates. Generation earns no measured hits."""
from hashlib import sha256
from importlib.metadata import version, PackageNotFoundError
import json
from pathlib import Path

from . import captured
from .isa import plan, extensions
from .semantic import VALUE_CLASSES

Z3_VERSION = '4.13.4.0'
R_TYPE = ('add', 'sub', 'xor', 'or', 'and', 'slt', 'sltu')
I_TYPE = ('addi', 'xori', 'ori', 'andi', 'slti', 'sltiu')
IMM_CLASSES = ('zero', 'positive', 'negative', 'minimum', 'maximum')


def profile(isa_plan):
    """Return the 170-bin profile without changing the full ISA denominator."""
    by_name = {i['name']: i for i in isa_plan['instructions']}
    missing = set(R_TYPE + I_TYPE) - by_name.keys()
    if missing:
        raise ValueError('integer profile needs pinned instructions: '+', '.join(sorted(missing)))
    goals = {}
    for name in R_TYPE + I_TYPE:
        fields = ('rs1', 'rs2') if name in R_TYPE else ('rs1', 'imm12')
        for field in fields:
            for value in IMM_CLASSES if field == 'imm12' else VALUE_CLASSES:
                identifier = f'sem_{name}_{field}:'+json.dumps([value], separators=(',', ':'))
                goals[identifier] = dict(instruction=name, field=field, value_class=value)
    return goals


def predicate(z3, value, kind, bits, immediate=False):
    if immediate:
        return {'zero': value == 0, 'minimum': value == 0x800, 'maximum': value == 0x7ff,
                'positive': z3.And(z3.UGT(value, 0), z3.ULT(value, 0x7ff)),
                'negative': z3.UGT(value, 0x800)}[kind]
    special = {'zero': 0, 'one': 1, 'all_ones': (1 << bits)-1,
               'signed_min': 1 << (bits-1), 'signed_max': (1 << (bits-1))-1}
    if kind in special:
        return value == special[kind]
    sign = value < 0 if kind == 'other_negative' else value >= 0
    return z3.And(sign, *(value != v for v in special.values()))


@captured.command
def generate(manifest, source_root, goal, work_dir, registers, seed=1, timeout_ms=1000):
    """Emit one pinned payload candidate and solver evidence. Never execute it."""
    if (type(seed) is not int or not 0 <= seed < 2**32 or type(timeout_ms) is not int
            or not 1 <= timeout_ms <= 60000):
        raise ValueError('seed must be uint32; timeout_ms must be 1..60000')
    if (not isinstance(registers, list) or len(registers) != 3 or len(set(registers)) != 3
            or any(type(r) is not int or not 1 <= r <= 31 for r in registers)):
        raise ValueError('registers must declare three distinct writable integer registers')
    pinned = plan(manifest, source_root)
    goals = profile(pinned['isa_plan'])
    xlen, _ = extensions(pinned['isa_plan']['manifest']['isa'])
    result = dict(schema='rvw.stimulus-candidate/1', status='unsupported', goal=goal, seed=seed,
                  profile='integer-170', supported_bins=len(goals), measured_hits=[], timeout_ms=timeout_ms,
                  full_plan_bins=sum(len(g.get('bins', [])) for g in pinned['groups']),
                  plan_sha256=sha256(json.dumps(pinned, sort_keys=True).encode()).hexdigest(),
                  registers=registers, xlen=xlen, solver_version=Z3_VERSION)
    if goal not in goals:
        return result | {'reason': 'goal outside bounded integer profile'}
    # Require a corresponding observer bin. The generator cannot invent a denominator.
    group, encoded_bin = goal.split(':', 1)
    configured = next((g for g in pinned['groups'] if g['name'] == group), None)
    if configured is None or json.loads(encoded_bin) not in configured.get('bins', []):
        return result | {'reason': 'goal absent from pinned semantic coverage plan'}
    try:
        installed = version('z3-solver')
    except PackageNotFoundError:
        return result | {'status': 'inconclusive', 'reason': 'install z3-solver=='+Z3_VERSION}
    if installed != Z3_VERSION:
        return result | {'status': 'inconclusive', 'reason': 'requires z3-solver=='+Z3_VERSION}
    import z3
    selected = goals[goal]
    record = next(i for i in pinned['isa_plan']['instructions'] if i['name'] == selected['instruction'])
    context = z3.Context()
    solver = z3.Solver(ctx=context)
    solver.set(timeout=timeout_ms, random_seed=seed)
    word = z3.BitVec('instruction', 32, ctx=context)
    a, b, imm = z3.BitVec('rs1_value', xlen, ctx=context), z3.BitVec('rs2_value', xlen, ctx=context), z3.BitVec('imm12', 12, ctx=context)
    rd, rs1, rs2 = registers
    solver.add(word & record['mask'] == record['value'])
    solver.add(z3.Extract(11, 7, word) == rd, z3.Extract(19, 15, word) == rs1)
    if selected['instruction'] in R_TYPE:
        solver.add(z3.Extract(24, 20, word) == rs2)
    else:
        solver.add(z3.Extract(31, 20, word) == imm)
    value = {'rs1': a, 'rs2': b, 'imm12': imm}[selected['field']]
    solver.add(predicate(z3, value, selected['value_class'], xlen, selected['field'] == 'imm12'))
    directory = Path(work_dir)
    directory.mkdir(parents=True, exist_ok=False)
    smt = solver.to_smt2()
    (directory/'constraints.smt2').write_text(smt)
    result['constraints_sha256'] = sha256(smt.encode()).hexdigest()
    verdict = solver.check()
    if verdict == z3.unsat:
        result.update(status='unsat', reason='bounded instruction template only; not an unreachable-bin proof')
    elif verdict != z3.sat:
        reason = solver.reason_unknown()
        result.update(status='timeout' if 'timeout' in reason else 'inconclusive', reason=reason)
    else:
        model = solver.model()
        values = {name: model.eval(v, model_completion=True).as_long()
                  for name, v in [('instruction', word), ('rs1', a), ('rs2', b), ('imm12', imm)]}
        source = ('.option norvc\n.option norelax\n'
                  f'li x{rs1}, 0x{values["rs1"]:x}\nli x{rs2}, 0x{values["rs2"]:x}\n'
                  '.global rvw_payload_start, rvw_payload_end\nrvw_payload_start:\n'
                  f'.word 0x{values["instruction"]:08x}\nrvw_payload_end:\n')
        (directory/'payload.S').write_text(source)
        result.update(status='generated', model=values, source_sha256=sha256(source.encode()).hexdigest(),
                      source=str(directory/'payload.S'),
                      reason='candidate only; compile, C1, full Spike comparison and payload sampling required')
    (directory/'candidate.json').write_text(json.dumps(result, indent=2)+'\n')
    return result
