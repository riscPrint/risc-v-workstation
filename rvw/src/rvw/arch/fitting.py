"""Offline selection of project-owned candidates. No simulator or tuner runs here."""
import math
from pathlib import Path

from .core import checked_report, compare, digest, read_json


def number(value, where):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f'{where} must be finite and nonnegative')
    return value


def roi_stats(path):
    """The model resets at ROI entry and dumps first at ROI exit."""
    raw = path.read_bytes()
    text = raw.decode()
    start = '---------- Begin Simulation Statistics ----------'
    end = '---------- End Simulation Statistics   ----------'
    if start not in text or end not in text.split(start, 1)[1]:
        raise ValueError(f'missing complete ROI stats block: {path}')
    block = text.split(start, 1)[1].split(end, 1)[0]
    stats = {}
    for line in block.splitlines():
        fields = line.split('#', 1)[0].split()
        if not fields:
            continue
        if len(fields) < 2 or fields[0] in stats:
            raise ValueError(f'ambiguous stats row: {line}')
        # Unused gem5 statistics can contain nan. Validate mapped values only.
        stats[fields[0]] = fields[1]
    return stats, digest(raw)


def fit(plan, project=None):
    """Select by training error only. Score the winner on a disjoint holdout."""
    if project is not None:
        from rvw.common.project import load_project
        load_project(project)
    path = Path(plan).resolve()
    raw = path.read_bytes()
    spec = read_json(raw)
    required = {'schema', 'rtl', 'candidates', 'train', 'held_out', 'events',
                'scope', 'uncertainty', 'unsupported'}
    if set(spec) != required or spec['schema'] != 'rvw.arch-fit-plan/1':
        raise ValueError('invalid rvw.arch-fit-plan/1 fields')
    for field in ('scope', 'uncertainty'):
        if not isinstance(spec[field], str) or not spec[field].strip():
            raise ValueError(f'{field} must be a nonempty statement')
    if not isinstance(spec['unsupported'], list) or any(not isinstance(s, str) or not s.strip() for s in spec['unsupported']):
        raise ValueError('unsupported must be an array of structure descriptions')
    for field in ('train', 'held_out'):
        names = spec[field]
        if not isinstance(names, list) or not names or any(not isinstance(n, str) or not n for n in names) or len(set(names)) != len(names):
            raise ValueError(f'{field} must contain distinct workload IDs')
    if set(spec['train']) & set(spec['held_out']):
        raise ValueError('train and held_out must be disjoint')
    events = spec['events']
    if not isinstance(events, list) or not events:
        raise ValueError('events must be nonempty')
    for event in events:
        if not isinstance(event, dict) or set(event) != {'name', 'rtl_metric', 'gem5_stat', 'unit', 'semantics'} or any(not isinstance(v, str) or not v.strip() for v in event.values()):
            raise ValueError('each event needs name, rtl_metric, gem5_stat, unit and semantics')
    if len({e['name'] for e in events}) != len(events):
        raise ValueError('duplicate event names')
    candidates = spec['candidates']
    if not isinstance(candidates, dict) or not candidates or any(not isinstance(k, str) or not k or not isinstance(v, str) for k, v in candidates.items()):
        raise ValueError('candidates must map distinct names to report paths')
    def resolve(value):
        return path.parent / value
    rtl_path = resolve(spec['rtl'])
    rtl, rows, rtl_hash = checked_report(rtl_path)
    if rtl['engine'] != 'rtl':
        raise ValueError('rtl must name an RTL report')
    selected = set(spec['train'] + spec['held_out'])
    if selected != set(rows):
        raise ValueError('split must cover exactly the report workloads')
    training_elfs = {rows[name]['elf_sha256'] for name in spec['train']}
    held_out_elfs = {rows[name]['elf_sha256'] for name in spec['held_out']}
    if training_elfs & held_out_elfs:
        raise ValueError('train and held_out ELF hashes must be disjoint')
    evidence = []
    errors = {}
    for name, candidate in candidates.items():
        candidate_path = resolve(candidate)
        # Reuse strict ELF, instruction count and run evidence checks.
        compare(rtl_path, candidate_path)
        model, model_rows, model_hash = checked_report(candidate_path)
        if model['engine'] != 'gem5':
            raise ValueError('candidate must name a gem5 report')
        per_workload = {}
        captures = []
        for workload in sorted(selected):
            measured = read_json(Path(rows[workload]['evidence']).read_bytes())['metrics']
            stats_path = Path(model_rows[workload]['evidence']).with_name('stats.txt')
            stats, stats_hash = roi_stats(stats_path)
            values = []
            for event in events:
                actual = number(measured.get(event['rtl_metric']), event['rtl_metric'])
                predicted = number(float(stats[event['gem5_stat']]), event['gem5_stat'])
                values.append({'event': event['name'], 'rtl': actual, 'gem5': predicted,
                               'error': number(abs(predicted - actual) / max(1, actual), 'event error')})
            per_workload[workload] = values
            captures.append({'workload': workload, 'stats': str(stats_path), 'sha256': stats_hash})
        errors[name] = per_workload
        evidence.append({'name': name, 'report': str(candidate_path), 'sha256': model_hash, 'stats': captures})
    def score(name, split):
        return sum(v['error'] for w in split for v in errors[name][w]) / (len(split) * len(events))
    training = {name: score(name, spec['train']) for name in candidates}
    winner = min(training, key=lambda name: (training[name], name))
    return {'schema': 'rvw.arch-fit/1', 'status': 'reported', 'selected': winner,
            'training_scores': training, 'held_out_score': score(winner, spec['held_out']),
            'selected_errors': errors[winner], 'train': spec['train'], 'held_out': spec['held_out'],
            'events': events, 'scope': spec['scope'], 'uncertainty': spec['uncertainty'],
            'unsupported': spec['unsupported'], 'plan_sha256': digest(raw),
            'rtl_sha256': rtl_hash, 'candidates': evidence,
            'limits': 'Offline candidate selection. No fidelity verdict or confidence interval. Holdout must not guide candidate creation. gem5 shows trends; RTL is the truth.'}
