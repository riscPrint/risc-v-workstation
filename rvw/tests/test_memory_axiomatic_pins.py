"""Cross-check synthetic canonical forms against the committed herd outcome pins.

The original six source files were checked outside the repository against the
source hashes in litmus-pins.json. No third-party source is vendored here.
"""
import hashlib
from itertools import product
import json
from pathlib import Path
import pytest
from rvw.memory.axiomatic import search


pytestmark = pytest.mark.fast


def event(identity, hart, order, kind, address=0, value=0):
    e = dict(id=identity, hart=hart, order=order, kind=kind, address=address, size=4,
             addr=[], data=[], ctrl=[])
    if kind == 'R':
        e['read'] = value
    elif kind == 'W':
        e['write'] = value
    else:
        e.update(pred='RW', succ='RW')
    return e


@pytest.mark.parametrize('model', ['rvwmo', 'ztso'])
@pytest.mark.parametrize('name', ['SB', 'MP', 'LB'])
@pytest.mark.parametrize('fenced', [False, True])
def test_complete_outcome_set_matches_pinned_reference(model, name, fenced):
    pins = json.loads((Path(__file__).resolve().parents[2]/'RiscvSim/tests/ordering/litmus-pins.json').read_text())
    allowed = []
    for first, second in product((0, 1), repeat=2):
        if name == 'SB':
            events = [event('a', 0, 0, 'W', 0, 1), event('b', 0, 2, 'R', 4, first),
                      event('c', 1, 0, 'W', 4, 1), event('d', 1, 2, 'R', 0, second)]
            projection = {'0:x7': first, '1:x7': second}
        elif name == 'MP':
            events = [event('a', 0, 0, 'W', 0, 1), event('b', 0, 2, 'W', 4, 1),
                      event('c', 1, 0, 'R', 4, first), event('d', 1, 2, 'R', 0, second)]
            projection = {'1:x5': first, '1:x7': second}
        else:
            events = [event('a', 0, 0, 'R', 0, first), event('b', 0, 2, 'W', 4, 1),
                      event('c', 1, 0, 'R', 4, second), event('d', 1, 2, 'W', 0, 1)]
            projection = {'0:x5': first, '1:x5': second}
        if fenced:
            events += [event('f', 0, 1, 'FENCE'), event('g', 1, 1, 'FENCE')]
        result = search(events, {(0, 4): 0, (4, 4): 0}, model)
        assert result['status'] in ('allowed', 'forbidden'), result
        if result['status'] == 'allowed':
            allowed.append(tuple(sorted(projection.items())))
    filename = name + ('+fence.rw.rws' if fenced else '') + '.litmus'
    key = 'tests/non-mixed-size/BASIC_2_THREAD/' + filename
    expected = pins['ztso_allowed_sha256' if model == 'ztso' else 'allowed_sha256'][key]
    actual = hashlib.sha256(json.dumps(sorted(allowed), separators=(',', ':')).encode()).hexdigest()
    assert actual == expected, (model, name, fenced, allowed)


def test_syntactic_data_dependencies_reject_a_thin_air_cycle():
    events = [event('a', 0, 0, 'R', 0, 1), event('b', 0, 1, 'W', 4, 1),
              event('c', 1, 0, 'R', 4, 1), event('d', 1, 1, 'W', 0, 1)]
    assert search(events, {(0, 4): 0, (4, 4): 0})['status'] == 'allowed'
    events[1]['data'] = ['a']; events[3]['data'] = ['c']
    assert search(events, {(0, 4): 0, (4, 4): 0})['status'] == 'forbidden'
