"""Resumable leakage campaigns: generate program pairs, follow coverage, reduce and deduplicate.

Each iteration picks a contract, takes a corpus program (or a new one from the grammar),
mutates the program and the secret pair, and runs one paired comparison with the case
adapter. Coverage keys come from the observations of the first case: per-instruction
retirement latency and bus or probe event shapes. A pair with new keys joins the corpus.
A violation is reduced with the paired reducer and deduplicated by its signature: the
sorted mnemonics of the reduced program, the contract and the channels that differ.
State is saved after each iteration; `resume` continues until the budget is used.
"""
import datetime
import hashlib
import json
import math
from pathlib import Path
import random
import time
from .pairs import run as run_pairs

DEST = [f'x{i}' for i in range(8, 16)]
SECRET = ['x6', 'x7']
PUBLIC = ['x5', 'x28', 'x29']
# Instruction classes. Operands from the secret registers are allowed only where the
# constant-time contract permits them (register arithmetic, store data).
GRAMMAR = {
    'alu': ['add', 'sub', 'xor', 'or', 'and', 'sll', 'srl', 'sra', 'slt', 'sltu'],
    'alui': ['addi', 'xori', 'ori', 'andi', 'slli', 'srli', 'srai', 'slti'],
    'mul': ['mul', 'mulh', 'mulhu', 'mulhsu'],
    'div': ['div', 'divu', 'rem', 'remu'],
    'load': ['lw', 'lh', 'lhu', 'lb', 'lbu'],
    'store': ['sw', 'sh', 'sb'],
    'branch': ['beq', 'bne', 'blt', 'bge', 'bltu', 'bgeu'],
}
CONTRACT_CLASSES = {
    'constant-time': ('alu', 'alui', 'mul', 'div', 'load', 'store', 'branch'),
    'speculative-constant-time': ('alu', 'alui', 'mul', 'div', 'load', 'store', 'branch'),
    'sandboxing': ('alu', 'alui', 'load', 'store', 'branch'),
}
BOUNDARY = [0, 1, 2, 0x7fffffff, 0x80000000, 0xffffffff, 0x55555555, 0xaaaaaaaa, 0x10000, 3]


def instruction(rng, cls, label):
    op = rng.choice(GRAMMAR[cls]); rd = rng.choice(DEST)
    src = lambda: rng.choice(SECRET + DEST + PUBLIC)
    if cls in ('alu', 'mul', 'div'):
        return [f'{op} {rd}, {src()}, {src()}']
    if cls == 'alui':
        imm = rng.randrange(0, 32) if op in ('slli', 'srli', 'srai') else rng.randrange(-2048, 2048)
        return [f'{op} {rd}, {src()}, {imm}']
    # Memory addresses and branch conditions use public registers only.
    if cls == 'load':
        return [f'{op} {rd}, {4*rng.randrange(0, 16)}(x30)']
    if cls == 'store':
        return [f'{op} {src()}, {4*rng.randrange(0, 16)}(x30)']
    return [f'{op} {rng.choice(PUBLIC)}, {rng.choice(PUBLIC)}, {label}f', f'add {rd}, {src()}, {src()}', f'{label}:']


def generate(rng, classes, length):
    body = []
    for i in range(length):
        body += instruction(rng, rng.choice(classes), 100+i)
    return body


def blocks(program):
    """Split into units that mutation keeps whole (a branch with its label)."""
    out, cur = [], []
    for line in program:
        cur.append(line)
        if cur[0].split()[0] in GRAMMAR['branch'] and not line.endswith(':'):
            continue
        out.append(cur); cur = []
    return out + ([cur] if cur else [])


def mutate(rng, program, classes):
    parts = blocks(program)
    choice = rng.randrange(3)
    label = 500+rng.randrange(10000)
    if choice == 0 or not parts:
        parts.insert(rng.randrange(len(parts)+1), instruction(rng, rng.choice(classes), label))
    elif choice == 1 and len(parts) > 1:
        parts.pop(rng.randrange(len(parts)))
    else:
        parts[rng.randrange(len(parts))] = instruction(rng, rng.choice(classes), label)
    return [line for p in parts for line in p]


def secret_pair(rng, previous=None):
    def value():
        return rng.choice(BOUNDARY) if rng.random() < 0.4 else rng.getrandbits(32)
    if previous and rng.random() < 0.5:
        a, b = (dict(p) for p in previous)
        k = rng.choice(SECRET); b[k] = b[k] ^ (1 << rng.randrange(32))  # bit-flip mutation
    else:
        a = {k: value() for k in SECRET}; b = {k: value() for k in SECRET}
    return [a, b] if a != b else [a, dict(b, x6=a['x6'] ^ 1)]


def coverage(response):
    """Coverage keys from one case's observations and program."""
    keys = set()
    obs = response.get('observations', {})
    lat = obs.get('retire_cycles', [])
    keys.update(f'lat:{min(v, 64)}' for v in lat)
    for name in ('dbus_trace', 'ibus_trace', 'bus_timing'):
        if name in obs:
            keys.add(f'{name}:{min(len(obs[name]), 64)}')
    for e in obs.get('branch_events', []) + obs.get('probe_events', []):
        keys.add(f'probe:{e.get("kind")}:{e.get("name")}:{e.get("taken", "")}:{e.get("predicted_taken", "")}')
    for k, v in obs.get('probe_counters', {}).items():
        keys.add(f'counter:{k}:{min(v, 64)}')
    return keys


def signature(program, channels):
    """Root-cause signature: the reduced program's mnemonics and the channels that differ."""
    ops = sorted({line.split()[0] for line in program if not line.endswith(':')})
    text = f'{",".join(ops)}|{",".join(sorted(channels))}'
    return text, hashlib.sha256(text.encode()).hexdigest()[:12]


def run(manifest, out, resume=False):
    manifest = Path(manifest).resolve()
    plan = json.loads(manifest.read_text())
    missing = sorted({'adapter_command', 'observations'} - plan.keys())
    if missing:
        raise ValueError('Security campaign requires ' + ', '.join(missing) +
                         '. Supply a paired RTL adapter and observation channels; see '
                         'docs/INTEGRATION_GUIDE.md#project-input-recipes.')
    out = Path(out).resolve()
    state_path = out/'state.json'
    if resume:
        state = json.loads(state_path.read_text())
    else:
        out.mkdir(parents=True, exist_ok=False)
        state = dict(schema='rvw.sec-campaign/1', iteration=0, pairs=0, seconds=0.0, corpus=[], coverage=[],
                     signatures={}, statuses={}, errors=[])
    contracts = plan.get('contracts', ['constant-time'])
    for c in contracts:
        if c not in CONTRACT_CLASSES:
            raise ValueError(f'unknown contract {c}')
    budget = plan.get('budget', {})
    max_pairs, max_seconds = budget.get('pairs', 20), budget.get('seconds', 1800)
    length = plan.get('length', [4, 12])
    seen = set(state['coverage'])
    started = time.monotonic(); spent = state['seconds']
    while state['pairs'] < max_pairs and spent + (time.monotonic()-started) < max_seconds:
        i = state['iteration']
        rng = random.Random(f'{plan.get("seed", 1)}:{i}')
        contract = contracts[i % len(contracts)]  # round-robin contract selection
        classes = [c for c in plan.get('classes', CONTRACT_CLASSES[contract]) if c in CONTRACT_CLASSES[contract]]
        parent = rng.choice(state['corpus']) if state['corpus'] and rng.random() < 0.8 else None
        if parent:
            program = mutate(rng, parent['program'], classes); secrets = secret_pair(rng, parent['secrets'])
        else:
            program = generate(rng, classes, rng.randint(*length)); secrets = secret_pair(rng)
        case = dict(contract=contract, clauses=plan.get('clauses', ['pc', 'memory', 'branch']),
                    observations=plan['observations'], public=plan.get('public', {}), program=program,
                    secrets=secrets, minimize_runs=0, timeout=plan.get('timeout', 1800),
                    adapter_command=[a if not a.endswith(('.json', '.S')) or a.startswith('/') else
                                     str(manifest.parent/a) for a in plan['adapter_command']])
        folder = out/f'pair-{i:04d}'
        folder.mkdir(exist_ok=True)
        path = folder/'manifest.json'; path.write_text(json.dumps(case, indent=2))
        report = run_pairs(path, folder/'run') if not (folder/'run').exists() else json.loads((folder/'run/report.json').read_text())
        status = report['comparison'].get('status', 'inconclusive') if report['complete'] or report['findings'] else 'inconclusive'
        state['statuses'][status] = state['statuses'].get(status, 0)+1
        if report.get('errors'):
            state['errors'].append(dict(pair=i, errors=report['errors'][:2]))
        response = folder/'run/initial-a/response.json'
        new = set()
        if response.exists():
            new = coverage(json.loads(response.read_text())) - seen
            seen |= new
            if new and status != 'ineligible':
                state['corpus'].append(dict(program=program, secrets=secrets, pair=i, new=sorted(new)))
        if status == 'violation':
            reduced = dict(case, minimize_runs=plan.get('minimize_runs', 12))
            rpath = folder/'reduce.json'; rpath.write_text(json.dumps(reduced, indent=2))
            r = run_pairs(rpath, folder/'reduced')
            witness = r['findings'][0] if r['findings'] else dict(program=program, comparison=report['comparison'])
            text, key = signature(witness['program'], witness['comparison'].get('channels', []))
            entry = state['signatures'].setdefault(key, dict(signature=text, first_pair=i, count=0,
                                                             program=witness['program'], secrets=secrets,
                                                             contracts=[]))
            entry['count'] += 1
            if contract not in entry['contracts']:
                entry['contracts'].append(contract)
        state['iteration'] += 1; state['pairs'] += 1
        state['seconds'] = spent + (time.monotonic()-started)
        state['coverage'] = sorted(seen)
        state_path.write_text(json.dumps(state, indent=2)+'\n')
    return finish(out, state, plan, max_pairs, max_seconds)


def finish(out, state, plan, max_pairs, max_seconds):
    sigs = state['signatures']
    eligible = state['statuses'].get('violation', 0)+state['statuses'].get('no_leak_observed', 0)
    # A clean result needs a stated share of the pairs run to be eligible, not just one of them.
    fraction = plan.get('min_eligible_fraction', 0.5)
    if not isinstance(fraction, (int, float)) or not 0 < fraction <= 1:
        raise ValueError('min_eligible_fraction must be in (0, 1]')
    minimum = max(1, math.ceil(fraction*state['pairs']))
    enough = eligible >= minimum
    status = 'violation' if sigs else 'no_leak_observed' if enough else 'inconclusive'
    tests = [dict(id=f'sec-campaign:{k}', status='fail', message=v['signature'],
                  signature='sec:campaign:'+v['signature']) for k, v in sorted(sigs.items())]
    if not sigs:
        t = dict(id='sec-campaign', status='pass' if enough else 'error', message=status)
        if not enough:
            t['inconclusive'] = f'{eligible} of {state["pairs"]} pairs eligible; minimum {minimum}'
        tests.append(t)
    results = dict(schema='rvw.results/1', run_id=out.name, suite='sec-campaign', core='project',
                   config='declared', source={}, created=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   tests=tests)
    (out/'results.json').write_text(json.dumps(results, indent=2)+'\n')
    report = dict(schema='rvw.sec/1', technique='campaign', status=status, complete=enough, eligible_pairs=eligible, min_eligible_pairs=minimum,
                  findings=[dict(key=k, **v) for k, v in sorted(sigs.items())], pairs=state['pairs'],
                  statuses=state['statuses'], coverage_keys=len(state['coverage']), corpus=len(state['corpus']),
                  budget=dict(pairs=max_pairs, seconds=max_seconds), seconds=round(state['seconds'], 1),
                  errors=state['errors'][-5:])
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    lines = ['# Leakage campaign', '', f'Status: `{status}`. Pairs: {state["pairs"]} '
             f'(budget {max_pairs} pairs, {max_seconds} s). Eligible: {eligible} (minimum {minimum}). '
             f'Outcomes: {state["statuses"]}.',
             f'Coverage keys: {len(state["coverage"])}. Corpus: {len(state["corpus"])} programs.', '',
             '`no_leak_observed` covers only these pairs. It does not mean secure.', '']
    if sigs:
        lines += ['| Signature | First pair | Count | Reduced program |', '|---|---|---|---|']
        lines += [f'| `{v["signature"]}` | {v["first_pair"]} | {v["count"]} | `{"; ".join(v["program"])}` |'
                  for v in sigs.values()]
    (out/'report.md').write_text('\n'.join(lines)+'\n')
    return report
