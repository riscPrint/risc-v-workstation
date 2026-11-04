import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3] / 'RiscvSim/tests/ordering'
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location('ordering_fixture', ROOT / 'fixture.py')
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)
sys.path.remove(str(ROOT))


def test_strict_translation():
    text = '''RISCV SB
{0:x5=1;0:x6=x;1:x6=y;}
 P0 | P1 ;
 sw x5,0(x6) | lw x7,0(x6) ;
 fence rw,rw | fence rw,rw ;
exists (1:x7=1)
'''
    programs = fixture.translate(text)
    assert programs == [[0x00100293, 0x00000313, 0x00532023, 0x0330000f],
                        [0x00400313, 0x00000013, 0x00032383, 0x0330000f]]


@pytest.mark.parametrize('asm', ['amoadd.w x1,x2,(x3)', 'lw x32,0(x1)', 'fence r,w', 'sw x1,4(x2)'])
def test_unsupported_instruction_refused(asm):
    with pytest.raises(ValueError):
        fixture.instruction(asm)


def test_checker_rejects_forbidden_and_incomplete_samples():
    reference = pinned_reference()
    case = reference['cases'][0]['test']
    samples = [{'test': case, 'harts': 2, 'complete': True,
                'observations': [{'state': {'0:x7': 2, '1:x7': 0}, 'count': 1}]}]
    samples += [sample_for(c) for c in reference['cases'][1:]]
    assert fixture.check(reference, samples)[0]['status'] == 'mismatch'
    samples[0]['complete'] = False
    assert fixture.check(reference, samples)[0]['status'] == 'inconclusive'
    with pytest.raises(ValueError):
        fixture.check(reference, samples * 2)
    with pytest.raises(ValueError):
        fixture.check(reference, [])


def test_empty_or_duplicate_reference_cannot_pass():
    with pytest.raises(ValueError):
        fixture.check({'cases': []}, [])
    case = {'test': 'SB', 'allowed': [{'0:x7': 0}]}
    sample = {'test': 'SB', 'harts': 2, 'complete': True,
              'observations': [{'state': {'0:x7': 0}, 'count': 1}]}
    with pytest.raises(ValueError):
        fixture.check({'cases': [case, case]}, [sample, sample])


def test_fixture_comparison_requires_pinned_complete_reference():
    import json
    pins = json.loads(fixture.PINS.read_text())
    case = next(iter(pins['cases']))
    sample = {'test': case, 'harts': 2, 'complete': True,
              'observations': [{'state': {'0:x7': 0, '1:x7': 0}, 'count': 1}]}
    reference = {'pins': pins, 'dut': 'not_run', 'cases': [
        {'test': case, 'allowed': [{'0:x7': 0, '1:x7': 0}]}]}
    with pytest.raises(ValueError, match='pinned'):
        fixture.check(reference, [sample])


def pinned_reference():
    import json
    from itertools import product
    pins = json.loads(fixture.PINS.read_text())
    cases = []
    for name in pins['cases']:
        keys = ['1:x5', '1:x7'] if '/MP' in name else ['0:x5', '1:x5'] if '/LB' in name else ['0:x7', '1:x7']
        states = [dict(zip(keys, v)) for v in product((0, 1), repeat=2)
                  if 'fence' not in name or v != ((1, 0) if '/MP' in name else (1, 1) if '/LB' in name else (0, 0))]
        cases.append({'test': name, 'allowed': states})
    return {'pins': pins, 'dut': 'not_run', 'cases': cases}


def sample_for(case):
    return {'test': case['test'], 'harts': 2, 'complete': True,
            'observations': [{'state': case['allowed'][0], 'count': 1}]}


def test_pinned_reference_rejects_changed_allowed_sets():
    reference = pinned_reference()
    samples = [sample_for(c) for c in reference['cases']]
    assert all(r['status'] == 'consistent' for r in fixture.check(reference, samples))
    reference['cases'][0]['allowed'].pop()
    with pytest.raises(ValueError, match='allowed states'):
        fixture.check(reference, samples)


def test_fenced_mp_and_lb_have_distinct_forbidden_states():
    reference = pinned_reference()
    samples = [sample_for(c) for c in reference['cases']]
    for sample in samples:
        if '/MP+' in sample['test']:
            sample['observations'] = [{'state': {'1:x5': 1, '1:x7': 0}, 'count': 1}]
        if '/LB+' in sample['test']:
            sample['observations'] = [{'state': {'0:x5': 1, '1:x5': 1}, 'count': 1}]
    rows = fixture.check(reference, samples)
    assert sum(r['status'] == 'mismatch' for r in rows) == 2
