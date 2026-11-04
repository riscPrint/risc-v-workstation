"""Bounded Bayesian optimization on a discrete project-owned parameter space."""
from copy import deepcopy
import math
from pathlib import Path
from statistics import mean

from . import core
from .dse import canonical, points
from .fitting import fit, number, roi_stats, validate_plan
from .statistics import interval
from rvw.results import write_json


def solve(matrix, vector):
    """Solve the positive definite GP covariance system by elimination."""
    rows = [list(row) + [v] for row, v in zip(matrix, vector)]
    for i in range(len(rows)):
        pivot = rows[i][i]
        rows[i] = [v / pivot for v in rows[i]]
        for j in range(len(rows)):
            if i != j:
                factor = rows[j][i]
                rows[j] = [a - factor*b for a, b in zip(rows[j], rows[i])]
    return [row[-1] for row in rows]


def propose(vectors, observations):
    """Unit RBF Gaussian process with fixed noise and expected improvement."""
    remaining = [i for i in range(len(vectors)) if i not in observations]
    if not observations:
        return remaining[0]
    seen = sorted(observations)
    def kernel(a, b):
        return math.exp(-sum((x-y)**2 for x, y in zip(a, b)) / 2)
    matrix = [[kernel(vectors[i], vectors[j]) + (1e-6 if i == j else 0)
               for j in seen] for i in seen]
    center = mean(observations.values())
    alpha = solve(matrix, [observations[i] - center for i in seen])
    best = min(observations.values())
    def improvement(i):
        k = [kernel(vectors[i], vectors[j]) for j in seen]
        mu = center + sum(a*b for a, b in zip(k, alpha))
        sigma = math.sqrt(max(1e-12, 1 - sum(a*b for a, b in zip(k, solve(matrix, k)))))
        z = (best - mu) / sigma
        return (best-mu) * (1 + math.erf(z / math.sqrt(2))) / 2 + sigma * math.exp(-z*z/2) / math.sqrt(2*math.pi)
    return max(remaining, key=lambda i: (improvement(i), -i))


def search(plan, out, project=None):
    path = Path(plan).resolve()
    raw = path.read_bytes()
    spec = core.read_json(raw)
    required = {'schema', 'fit', 'parameters', 'budget', 'repeats', 'timeout_s'}
    if set(spec) != required or spec['schema'] != 'rvw.arch-search/1':
        raise ValueError('invalid rvw.arch-search/1 fields')
    for key, low, high in (('budget', 1, 32), ('repeats', 2, 10)):
        if type(spec[key]) is not int or not low <= spec[key] <= high:
            raise ValueError(f'{key} must be between {low} and {high}')
    fit_spec = deepcopy(spec['fit'])
    validate_plan({**fit_spec, 'candidates': {'search': 'pending'}})
    if fit_spec['candidates'] != {}:
        raise ValueError('search fit.candidates must be empty')
    p, _, baseline = core.settings(project)
    candidates = points(baseline, {'schema': 'rvw.arch-sweep/1', 'parameters': spec['parameters'],
                                   'max_points': 32, 'timeout_s': spec['timeout_s']})
    if any(c['memory_latency'] != baseline['memory_latency'] or 'soc' in c for c in candidates):
        raise ValueError('fitting requires unchanged RTL memory latency and supported topology')
    rtl_path = (path.parent / fit_spec['rtl']).resolve()
    rtl, rtl_rows, rtl_sha = core.checked_report(rtl_path)
    names = fit_spec['train'] + fit_spec['held_out']
    if rtl['engine'] != 'rtl' or set(names) != set(rtl_rows):
        raise ValueError('split must cover exactly the RTL report workloads')
    if {rtl_rows[w]['elf_sha256'] for w in fit_spec['train']} & {rtl_rows[w]['elf_sha256'] for w in fit_spec['held_out']}:
        raise ValueError('train and held_out ELF hashes must be disjoint')
    budget = min(spec['budget'], len(candidates))
    if (budget * len(fit_spec['train']) + len(fit_spec['held_out'])) * spec['repeats'] > 256:
        raise ValueError('search exceeds 256 model processes')
    _, _, out, files, context = core.prepare(p.path, ','.join(names), out)
    for key in ('core', 'config', 'memory_latency'):
        if context[key] != rtl[key]:
            raise ValueError(f'RTL {key} differs from selected project')
    if any(f['elf_sha256'] != rtl_rows[f['id']]['elf_sha256'] for f in files):
        raise ValueError('RTL ELF hashes differ from selected benchmarks')
    (out / 'inputs/search.json').write_bytes(raw)
    # Categorical values use one-hot encoding. Numeric values use range scaling.
    vectors = []
    for candidate in candidates:
        vector = []
        for key, values in sorted(spec['parameters'].items()):
            node = candidate
            for part in key.split('.'):
                node = node[int(part)] if isinstance(node, list) else node[part]
            if all(type(v) in (int, float) for v in values):
                span = max(values) - min(values)
                vector.append((node - min(values)) / span if span else 0)
            else:
                vector.extend(float(node == v) for v in values)
        vectors.append(vector)
    observations, trials = {}, []
    tools = set()
    def measure(index, split, repeat):
        directory = out / f'point-{index}' / f'{split}-{repeat}'
        inputs = directory / 'inputs'
        inputs.mkdir(parents=True)
        (inputs / 'model.py').write_bytes((out / 'inputs/model.py').read_bytes())
        description = canonical(candidates[index])
        (inputs / 'description.json').write_bytes(description)
        report = core.run_models(directory, [f for f in files if f['id'] in fit_spec[split]],
                                 {**context, 'description_sha256': core.digest(description)}, spec['timeout_s'])
        tools.add(report['tool']['sha256'])
        if len(tools) != 1:
            raise ValueError('gem5 binary changed during search')
        errors = []
        for row in report['benchmarks']:
            actual = rtl_rows[row['id']]
            if row['instret'] != actual['instret']:
                raise ValueError('ROI instruction count differs')
            metrics = core.read_json(Path(actual['evidence']).read_bytes())['metrics']
            stats, _ = roi_stats(Path(row['evidence']).with_name('stats.txt'))
            for event in fit_spec['events']:
                x = number(metrics.get(event['rtl_metric']), event['rtl_metric'])
                y = number(float(stats[event['gem5_stat']]), event['gem5_stat'])
                errors.append(number(abs(y-x) / max(1, x), 'error'))
        return mean(errors), report, directory / 'gem5.json'
    for _ in range(budget):
        index = propose(vectors, observations)
        measurements = [measure(index, 'train', r) for r in range(spec['repeats'])]
        scores = [m[0] for m in measurements]
        observations[index] = mean(scores)
        trials.append({'point': index, 'description': candidates[index], 'training': interval(scores),
                       'reports': [str(m[2]) for m in measurements]})
        write_json(out / 'progress.json', {'trials': trials, 'status': 'inconclusive'})
    winner = min(observations, key=lambda i: (observations[i], i))
    held_scores, reports = [], []
    for repeat in range(spec['repeats']):
        score, held, _ = measure(winner, 'held_out', repeat)
        held_scores.append(score)
        train_path = out / f'point-{winner}' / f'train-{repeat}' / 'gem5.json'
        train = core.read_json(train_path.read_bytes())
        combined = {**train, 'benchmarks': train['benchmarks'] + held['benchmarks']}
        combined_path = out / f'selected-{repeat}.json'
        write_json(combined_path, combined)
        final_plan = {**fit_spec, 'rtl': str(rtl_path), 'candidates': {'selected': str(combined_path)}}
        plan_path = out / f'fit-{repeat}.json'
        write_json(plan_path, final_plan)
        reports.append(fit(plan_path))
    if core.checked_report(rtl_path)[2] != rtl_sha:
        raise ValueError('RTL report changed during search')
    result = {'schema': 'rvw.arch-search-result/1', 'status': 'reported', 'selected': winner,
              'method': 'discrete RBF Gaussian process expected improvement',
              'plan_sha256': core.digest(raw), 'trials': trials,
              'held_out': interval(held_scores), 'reports': reports,
              'limits': 'Intervals describe repeat variation only. Fixed seeds and deterministic models can give zero width. No fidelity verdict. RTL and held-out workloads must be independent of tuning.'}
    write_json(out / 'search.json', result)
    return result
