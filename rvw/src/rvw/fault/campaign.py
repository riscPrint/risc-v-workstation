"""Fault injection campaigns for functional safety (`rvw fault`).

Sites come from the design database (C6 `signals`, kind `reg`). A plan samples
stuck-at-0, stuck-at-1 and transient bit-flip faults with a seed and records the
population. Each fault runs through the core adapter (C1 `run --fault FILE`). The
adapter must confirm the injection in `details.fault`. The result is classified
against the golden run's C2 trace:

- `detected`: the run reported a failure status or a declared detection mechanism fired.
- `silent_corruption`: the run passed but its architectural trace differs from the golden run.
- `safe`: the run passed with the golden architectural trace.
- `timeout`: the run did not end (detected only when the profile declares a watchdog).
- `not_injected`: the adapter did not confirm the injection; it is not in the denominator.
- `inconclusive`: the harness failed or evidence is missing.

The report gives counts, denominators and diagnostic coverage with a confidence
interval. It is an estimate from simulation, not measured hardware reliability,
and not evidence of ISO 26262 compliance or tool qualification.
"""
from __future__ import annotations

import datetime as _dt
import fnmatch
import hashlib
import json
import math
import random
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from rvw.common.proc import run_group

PLAN_SCHEMA = 'rvw.fault-plan/1'
FAULT_SCHEMA = 'rvw.fault/1'
REPORT_SCHEMA = 'rvw.fault-report/1'
KINDS = ('stuck0', 'stuck1', 'flip')
COMPARE = ('pc', 'insn', 'rd', 'rd_wdata', 'mem_addr', 'mem_wmask', 'mem_wdata', 'trap', 'mode')
CLASSES = ('detected', 'silent_corruption', 'safe', 'timeout', 'not_injected', 'inconclusive')


# -- sites ----------------------------------------------------------------------------------
def sites(db, *, include=('*',), exclude=(), generated=False):
    """Register bit sites from a design database: [{'path', 'width', 'clock_domain'}]."""
    conn = sqlite3.connect(Path(db).resolve().as_uri() + '?mode=ro', uri=True)
    try:
        schema = dict(conn.execute('SELECT key, value FROM meta').fetchall()).get('schema', '')
        if not str(schema).startswith('rvw.designdb/'):
            raise ValueError(f'{db}: not an rvw design database')
        columns = {row[1] for row in conn.execute('PRAGMA table_info(signals)')}
        for needed in ('path', 'width', 'kind'):
            if needed not in columns:
                raise ValueError(f'{db}: signals table lacks {needed}')
        optional = [c for c in ('generated', 'pruned', 'clock_domain_id') if c in columns]
        rows = conn.execute(f'SELECT path, width, kind{"".join(", " + c for c in optional)} FROM signals '
                            "WHERE kind = 'reg'").fetchall()
    finally:
        conn.close()
    out = []
    for row in rows:
        record = dict(zip(['path', 'width', 'kind', *optional], row))
        if record.get('pruned') or (record.get('generated') and not generated):
            continue
        if not isinstance(record['width'], int) or record['width'] <= 0:
            continue
        if not any(fnmatch.fnmatchcase(record['path'], g) for g in include):
            continue
        if any(fnmatch.fnmatchcase(record['path'], g) for g in exclude):
            continue
        out.append({'path': record['path'], 'width': record['width'],
                    'clock_domain': record.get('clock_domain_id')})
    return sorted(out, key=lambda s: s['path'])


def listed_sites(path, *, include=('*',), exclude=()):
    """Register bit sites from a site list file ({"sites": [{"path", "width"}]})."""
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict) or not isinstance(data.get('sites'), list):
        raise ValueError(f'{path}: expected {{"sites": [...]}}')
    out = []
    for s in data['sites']:
        if not isinstance(s, dict) or not isinstance(s.get('path'), str) or type(s.get('width')) is not int or s['width'] <= 0:
            raise ValueError(f'{path}: each site needs a path and a positive integer width')
        if any(fnmatch.fnmatchcase(s['path'], g) for g in include) and not any(fnmatch.fnmatchcase(s['path'], g) for g in exclude):
            out.append({'path': s['path'], 'width': s['width'], 'clock_domain': s.get('clock_domain')})
    return sorted(out, key=lambda s: s['path'])


# -- plan -----------------------------------------------------------------------------------
def plan(site_list, *, kinds=KINDS, window=(0, 1000), samples=100, seed=1, duration=None, db_sha256=None):
    """Seeded sample of faults. Permanent stuck-at faults start at `window[0]` unless `duration`
    is given; transient flips are single-cycle upsets at a uniform cycle in `window`."""
    if not site_list:
        raise ValueError('no fault sites selected')
    start, end = window
    if not 0 <= start < end:
        raise ValueError('window must be START < END')
    for kind in kinds:
        if kind not in KINDS:
            raise ValueError(f'fault kind must be one of {", ".join(KINDS)}')
    bits = sum(s['width'] for s in site_list)
    population = {k: bits * (end - start) for k in kinds}
    rng = random.Random(seed)
    total = sum(population.values())
    faults, seen = [], set()
    exhaustive = total <= samples
    candidates = []
    if exhaustive:
        for kind in kinds:
            for site in site_list:
                for bit in range(site['width']):
                    for cycle in range(start, end):
                        candidates.append((kind, site['path'], bit, cycle))
    else:
        weights = [s['width'] for s in site_list]
        while len(candidates) < samples:
            kind = rng.choice(list(kinds))
            site = rng.choices(site_list, weights)[0]
            key = (kind, site['path'], rng.randrange(site['width']), rng.randrange(start, end))
            if key not in seen:
                seen.add(key)
                candidates.append(key)
    for index, (kind, path, bit, cycle) in enumerate(candidates):
        fault = {'id': f'f{index:05d}', 'kind': kind, 'site': path, 'bit': bit, 'cycle': cycle}
        if kind == 'flip':
            fault['duration'] = 1
        elif duration is not None:
            fault['duration'] = duration
        faults.append(fault)
    return {'schema': PLAN_SCHEMA, 'seed': seed, 'kinds': list(kinds), 'window': [start, end],
            'duration': duration, 'sites': site_list, 'site_bits': bits, 'population': population,
            'population_total': total, 'sampling': 'exhaustive' if exhaustive else 'uniform-random',
            'faults': faults, 'design_db_sha256': db_sha256}


# -- runs -----------------------------------------------------------------------------------
def run_adapter(adapter, elf, out, *, fault=None, max_cycles=None, timeout=600, extra=()):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    command = [*adapter, 'run', '--elf', str(elf), '--out', str(out), '--rvfi-trace', *extra]
    if max_cycles is not None:
        command += ['--max-cycles', str(max_cycles)]
    if fault is not None:
        path = out / 'fault.json'
        path.write_text(json.dumps({'schema': FAULT_SCHEMA, 'faults': [fault]}, indent=2) + '\n')
        command += ['--fault', str(path)]
    result = run_group(command, timeout=timeout, capture=True)
    (out / 'adapter.log').write_text((result.stdout or '') + (result.stderr or ''))
    try:
        c1 = json.loads((out / 'result.json').read_text())
    except (OSError, ValueError):
        c1 = None
    return c1, result.timed_out


def architectural(path):
    """Architectural records of a C2 trace (cycle and timing fields dropped)."""
    records, end = [], None
    with Path(path).open() as stream:
        header = json.loads(next(stream))
        if not str(header.get('schema', '')).startswith('rvw.rvfi/'):
            raise ValueError('not a C2 trace')
        for line in stream:
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get('event') == 'end':
                end = record.get('status')
                continue
            if record.get('event') == 'trap':
                records.append(('trap', record.get('cause'), record.get('tval')))
                continue
            if 'event' in record:
                continue
            records.append(tuple(record.get(k) for k in COMPARE))
    return records, end


def first_difference(a, b):
    for index, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return index
    return None if len(a) == len(b) else min(len(a), len(b))


def classify(c1, timed_out, golden, out, *, detections=None, watchdog=False):
    """Return (classification, evidence)."""
    detections = detections or {}
    if c1 is None:
        return ('timeout' if timed_out else 'inconclusive'), {'reason': 'no C1 result'}
    details = c1.get('details') or {}
    applied = details.get('fault') or {}
    if applied.get('applied') is not True:
        return 'not_injected', {'reason': applied.get('reason') or 'the adapter did not confirm the injection'}
    status = c1.get('status')
    fired = sorted(set(details.get('detections') or []) & set(detections.get('mechanisms', [])) |
                   ({detections['status'][status]} if status in detections.get('status', {}) else set()))
    evidence = {'status': status, 'applied': applied}
    if status == 'timeout' or timed_out:
        evidence['detected_by'] = ['watchdog'] if watchdog else []
        return ('detected' if watchdog else 'timeout'), evidence
    if status == 'error' or c1.get('inconclusive'):
        return 'inconclusive', {**evidence, 'reason': c1.get('message') or c1.get('inconclusive') or 'adapter error'}
    trace = (c1.get('artifacts') or {}).get('rvfi_trace')
    if fired or status in ('fail', 'assert', 'rvfi_error'):
        evidence['detected_by'] = fired or [f'status:{status}']
        return 'detected', evidence
    if status != 'pass':
        return 'inconclusive', {**evidence, 'reason': f'unknown status {status}'}
    if not trace or not (Path(out) / trace).is_file():
        return 'inconclusive', {**evidence, 'reason': 'passing run without a C2 trace'}
    records, end = architectural(Path(out) / trace)
    if end != 'pass':
        return 'inconclusive', {**evidence, 'reason': 'C2 trace has no passing end'}
    diff = first_difference(records, golden)
    if diff is None:
        return 'safe', evidence
    evidence['first_difference'] = diff
    return 'silent_corruption', evidence


def wilson(successes, total, z=1.96):
    if not total:
        return None
    p = successes / total
    centre = (p + z * z / (2 * total)) / (1 + z * z / total)
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def report(plan_data, outcomes):
    counts = {c: 0 for c in CLASSES}
    per_site = {}
    for outcome in outcomes:
        counts[outcome['classification']] += 1
        site = per_site.setdefault(outcome['site'], {c: 0 for c in CLASSES})
        site[outcome['classification']] += 1
    injected = sum(counts[c] for c in ('detected', 'silent_corruption', 'safe', 'timeout'))
    dangerous = counts['detected'] + counts['silent_corruption'] + counts['timeout']
    coverage = counts['detected'] / dangerous if dangerous else None
    return {
        'schema': REPORT_SCHEMA, 'counts': counts, 'planned': len(outcomes), 'injected': injected,
        'population_total': plan_data['population_total'], 'sampling': plan_data['sampling'],
        'sampled_fraction': round(len(outcomes) / plan_data['population_total'], 8) if plan_data['population_total'] else None,
        'diagnostic_coverage': None if coverage is None else round(coverage, 4),
        'diagnostic_coverage_95': wilson(counts['detected'], dangerous),
        'safe_fraction': round(counts['safe'] / injected, 4) if injected else None,
        'unresolved': [o['id'] for o in outcomes if o['classification'] in ('timeout', 'inconclusive', 'not_injected')],
        'per_site': per_site,
        'definitions': 'diagnostic coverage = detected / (detected + silent_corruption + timeout); '
                       'safe and not_injected faults are outside that denominator',
        'scope': 'simulation estimate over the sampled faults; not measured hardware reliability; '
                 'no ISO 26262 compliance or tool qualification claim',
    }


def run_campaign(plan_data, adapter, elf, out, *, jobs=1, max_cycles=None, timeout=600, detections=None,
                 watchdog=False, extra=()):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    golden_c1, golden_timeout = run_adapter(adapter, elf, out / 'golden', max_cycles=max_cycles, timeout=timeout,
                                            extra=extra)
    if golden_c1 is None or golden_c1.get('status') != 'pass' or golden_timeout:
        raise ValueError('the golden run did not pass; no fault can be classified')
    trace = (golden_c1.get('artifacts') or {}).get('rvfi_trace')
    if not trace:
        raise ValueError('the golden run has no C2 trace')
    golden, end = architectural(out / 'golden' / trace)
    if end != 'pass':
        raise ValueError('the golden C2 trace has no passing end')

    def one(fault):
        directory = out / 'faults' / fault['id']
        c1, timed_out = run_adapter(adapter, elf, directory, fault=fault, max_cycles=max_cycles,
                                    timeout=timeout, extra=extra)
        classification, evidence = classify(c1, timed_out, golden, directory, detections=detections,
                                            watchdog=watchdog)
        return {**fault, 'classification': classification, 'evidence': evidence}

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        outcomes = list(pool.map(one, plan_data['faults']))
    summary = report(plan_data, outcomes)
    summary['golden_instructions'] = sum(1 for r in golden if r[0] != 'trap')
    summary['elf_sha256'] = hashlib.sha256(Path(elf).read_bytes()).hexdigest()
    summary['plan_seed'] = plan_data['seed']
    (out / 'outcomes.json').write_text(json.dumps(outcomes, indent=2) + '\n')
    (out / 'report.json').write_text(json.dumps(summary, indent=2) + '\n')
    write_c3(outcomes, plan_data, out)
    return summary, outcomes


def write_c3(outcomes, plan_data, out):
    created = _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    tests = []
    for outcome in outcomes:
        test = {'id': outcome['id'], 'classification': outcome['classification'], 'fault': {
            k: outcome[k] for k in ('kind', 'site', 'bit', 'cycle') if k in outcome}, 'evidence': outcome['evidence']}
        if outcome['classification'] in ('detected', 'safe'):
            test['status'] = 'pass'
        elif outcome['classification'] == 'silent_corruption':
            test.update(status='fail', signature=f'fault:sdc:{outcome["site"]}',
                        message=f'silent corruption from {outcome["kind"]} at {outcome["site"]}[{outcome["bit"]}]',
                        message_complete=True)
        else:
            test.update(status='error', signature='inconclusive', inconclusive=outcome['classification'])
        tests.append(test)
    results = {'schema': 'rvw.results/1', 'run_id': f'{created.replace(":", "-")}-fault-campaign',
               'suite': 'fault-campaign', 'core': 'adapter', 'config': f'seed-{plan_data["seed"]}',
               'created': created, 'source': {}, 'tests': tests}
    (Path(out) / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
