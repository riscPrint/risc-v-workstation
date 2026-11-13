"""Repeated three-size scheduling studies built on the existing C1 runner."""
from collections import defaultdict
from statistics import mean
from pathlib import Path
import math

from .statistics import interval
from . import sched
from rvw.results import write_json


def regression(samples):
    grouped = defaultdict(list)
    for sample in samples:
        grouped[sample['count']].append(sample)
    if len(grouped) < 3:
        raise ValueError('at least three distinct stream sizes are required')
    sizes = sorted(grouped)
    xmean = mean(sizes)
    variance = sum((n-xmean)**2 for n in sizes)
    result = {}
    for name in ('rtl', 'mca'):
        values = [mean(row[name+'_cycles'] for row in grouped[n]) for n in sizes]
        ymean = mean(values)
        slope = sum((n-xmean)*(v-ymean) for n, v in zip(sizes, values))/variance
        if slope <= 0:
            raise ValueError('nonpositive scheduling slope')
        intercept = ymean-slope*xmean
        adjacent = [(b-a)/(n-m) for m, n, a, b in zip(sizes, sizes[1:], values, values[1:])]
        deviation = max(abs(v-slope)/slope for v in adjacent)
        result[name] = dict(slope=slope, intercept=intercept, adjacent_slopes=adjacent,
                            nonlinear=deviation > 0.05, maximum_relative_slope_deviation=deviation,
                            max_residual_cycles=max(abs(v-(intercept+slope*n)) for n,v in zip(sizes,values)))
    return dict(**result, sizes=sizes, nonlinearity_threshold=0.05,
                error_percent=100*(result['mca']['slope']/result['rtl']['slope']-1))


def study(description_path, out, project=None, count=32, repeats=3, timeout=600,
          cc='riscv64-unknown-elf-gcc', mca='llvm-mca'):
    sched.integer(count, 'count', 16, 128)
    sched.integer(repeats, 'repeats', 3, 10)
    description = sched.description(description_path)
    for c in description['classes']:
        throughput = min(description['issue_width'], description['resources'][c['resource']] / c['occupancy'])
        if math.ceil(c['latency'] * throughput) > 8:
            raise ValueError('eight independent register chains cannot hide declared latency')
    out = Path(out).resolve(); out.mkdir(parents=True, exist_ok=False)
    rows = []
    for seed in range(1, repeats+1):
        for size in (count, count*2):
            result = sched.measure(description_path, out / f'seed{seed}-count{size}',
                                   project=project, count=size, timeout=timeout, cc=cc, mca=mca, seed=seed)
            rows.extend(dict(row, seed=seed) for row in result['samples'])
    summary = []
    for c in description['classes']:
        for mode in ('dependent', 'independent'):
            samples = [r for r in rows if r['class'] == c['name'] and r['mode'] == mode]
            estimates = [regression([r for r in samples if r['seed'] == seed]) for seed in range(1,repeats+1)]
            summary.append(dict(class_name=c['name'], mode=mode, repeats=estimates,
                rtl_slope=interval([r['rtl']['slope'] for r in estimates]),
                mca_slope=interval([r['mca']['slope'] for r in estimates]),
                signed_error_percent=interval([r['error_percent'] for r in estimates]),
                nonlinear=any(r['rtl']['nonlinear'] or r['mca']['nonlinear'] for r in estimates)))
    report = dict(schema='rvw.sched-study/1', status='reported', samples=rows, classes=summary,
                  seeds=list(range(1,repeats+1)), mem_latency=0, sizes=[count,count*2,count*4],
                  model_kind='builtin-baseline', generated_model_accuracy='inconclusive',
                  limits=['retirement slopes include pipeline limits', 'middle size has two measurements per seed',
                          'intervals describe observed seed variation only',
                          'mixed held-out, branch, bypass and variable-latency kernels remain open'])
    write_json(out / 'report.json', report)
    return report
