"""Small statistical reports. Intervals describe observed repeat variation only."""
import math
import random
from statistics import mean


def interval(values):
    if len(values) < 2:
        return {'n': len(values), 'mean': mean(values), 'ci95': None,
                'status': 'inconclusive'}
    rng = random.Random(0)
    samples = sorted(mean(rng.choices(values, k=len(values))) for _ in range(4000))
    return {'n': len(values), 'mean': mean(values),
            'ci95': [samples[99], samples[3899]], 'status': 'reported',
            'method': 'percentile bootstrap mean, 4000 resamples, seed 0'}


def correlation(pairs):
    n = len(pairs)
    if n < 3:
        return {'n': n, 'pearson_r': None, 'status': 'inconclusive',
                'reason': 'At least three workloads are required.'}
    x, y = zip(*pairs)
    dx = [v - mean(x) for v in x]
    dy = [v - mean(y) for v in y]
    denominator = math.sqrt(sum(v*v for v in dx) * sum(v*v for v in dy))
    return {'n': n, 'pearson_r': max(-1, min(1, sum(a*b for a, b in zip(dx, dy)) / denominator)) if denominator else None,
            'status': 'reported' if denominator else 'inconclusive',
            'reason': '' if denominator else 'A counter is constant.'}
