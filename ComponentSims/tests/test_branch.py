"""Native engine checks against a separate scalar reference."""
import json
import random
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]




def run(engine, trace, *args):
    return subprocess.run([str(engine), *map(str, args)], input=trace,
                          text=True, capture_output=True)


def encode(n, branches):
    return f'rvw.branch-trace/1 {n}\n' + ''.join(
        f'B {ordinal} {pc:x} {taken}\n' for ordinal, pc, taken in branches) + 'END\n'


@pytest.mark.parametrize('model', ['bimodal', 'gshare', 'perfect'])
@pytest.mark.parametrize('shift', [0, 1, 2])
def test_scalar_reference(engine, model, shift):
    rng = random.Random(27)
    branches = [(i, rng.randrange(64) * 2, rng.randrange(2))
                for i in range(1, 501, 3)]
    counters, history, misses = [1] * 8, 0, 0
    for ordinal, pc, taken in branches:
        index = ((pc >> shift) ^ (history if model == 'gshare' else 0)) & 7
        prediction = taken if model == 'perfect' else counters[index] >= 2
        if ordinal > 20:
            misses += prediction != taken
        counters[index] = min(3, counters[index] + 1) if taken else max(0, counters[index] - 1)
        history = ((history << 1) | taken) & 3
    result = run(engine, encode(500, branches), model, 8, 2, shift, 20)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data['direction_misses'] == misses
    assert data['instructions'] == 480
    assert data['mpki'] == pytest.approx(misses * 1000 / 480)
    assert data['rtl_comparison'] == 'inconclusive'


def test_saturation_and_warmup(engine):
    branches = [(i + 1, 0x100, t) for i, t in enumerate([1]*8 + [0]*8)]
    data = json.loads(run(engine, encode(20, branches), 'bimodal', 1, 0, 1, 0).stdout)
    assert data['direction_misses'] == 3  # weak NT miss; two misses after saturated T
    assert data['mpki'] == 150
    data = json.loads(run(engine, encode(20, branches), 'bimodal', 1, 0, 1, 8).stdout)
    assert data['direction_misses'] == 2
    assert data['instructions'] == 12


@pytest.mark.parametrize('trace,args', [
    ('rvw.branch-trace/1 1\n', []),
    ('rvw.branch-trace/1 0\nEND\n', []),
    ('rvw.branch-trace/1 2\nB 1 100 2\nEND\n', []),
    ('rvw.branch-trace/1 2\nB 1 100 0\nB 1 100 1\nEND\n', []),
    ('rvw.branch-trace/1 2\nB 3 100 0\nEND\n', []),
    ('rvw.branch-trace/1 2\nB 1 xyz 0\nEND\n', []),
    ('rvw.branch-trace/1 2\nEND\nB 1 100 0\n', []),
    ('rvw.branch-trace/1 2\nEND\n', ['tage-sc-l']),
    ('rvw.branch-trace/1 2\nEND\n', ['bimodal', 3]),
    ('rvw.branch-trace/1 2\nEND\n', ['bimodal', 8, 2, 1, 2]),
])
def test_refuse_invalid(engine, trace, args):
    result = run(engine, trace, *args)
    assert result.returncode == 2
    assert not result.stdout


def test_no_branches_and_reset(engine):
    data = json.loads(run(engine, encode(10, [])).stdout)
    assert data['mpki'] == 0 and data['branches'] == 0
    trace = encode(1, [(1, 0x100, 1)])
    assert run(engine, trace).stdout == run(engine, trace).stdout
