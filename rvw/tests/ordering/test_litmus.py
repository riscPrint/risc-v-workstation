import importlib.util
from pathlib import Path
import pytest

SPEC = importlib.util.spec_from_file_location('ordering_litmus',
    Path(__file__).resolve().parents[3] / 'RiscvSim/tests/ordering/litmus.py')
litmus = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(litmus)

OUTPUT = '''Test SB Allowed
States 2
0:x7=0; 1:x7=1;
0:x7=1; 1:x7=0;
Ok
Observation SB Never 0 2
'''


def test_allowed_and_forbidden():
    allowed = litmus.parse_states(OUTPUT)
    sample = {'harts': 2, 'complete': True,
              'observations': [{'state': {'0:x7': 0, '1:x7': 1}, 'count': 10}]}
    result = litmus.compare(allowed, sample)
    assert result['status'] == 'consistent'
    assert result['permitted_not_observed'] == [{'0:x7': 1, '1:x7': 0}]
    assert result['exhaustive_proof'] is False
    sample['observations'][0]['state']['1:x7'] = 0
    assert litmus.compare(allowed, sample)['status'] == 'mismatch'


@pytest.mark.parametrize('text', ['', OUTPUT.replace('States 2', 'States 3'),
    OUTPUT.replace('Observation SB Never 0 2', ''), OUTPUT.replace('1:x7=0', '1:x8=0'),
    OUTPUT.replace('1:x7=0', '1:x7=bogus'), OUTPUT.replace('States 2', 'States 0')])
def test_bad_reference_output(text):
    with pytest.raises(ValueError):
        litmus.parse_states(text)


@pytest.mark.parametrize('sample', [
    {}, {'harts': 1, 'complete': True, 'observations': []},
    {'harts': 2, 'complete': True, 'observations': []},
    {'harts': 2, 'complete': False, 'observations': [{'count': 1}]},
    {'harts': 2, 'complete': True, 'observations': [{'count': 0, 'state': {'0:x7': 0}}]},
    {'harts': 2, 'complete': True, 'observations': [{'count': 1, 'state': {'0:x7': 0}}]},
])
def test_missing_samples_inconclusive(sample):
    assert litmus.compare(litmus.parse_states(OUTPUT), sample)['status'] == 'inconclusive'


def test_pin_library_changes(tmp_path):
    (tmp_path / 'model.cat').write_text('acyclic po')
    original = litmus.tree_digest(tmp_path)
    (tmp_path / 'model.cat').write_text('empty po')
    assert original != litmus.tree_digest(tmp_path)


def test_native_official_model(tmp_path):
    import json
    import os
    import shutil
    tests = os.environ.get('RVW_LITMUS_TESTS')
    source = os.environ.get('RVW_HERD_SOURCE')
    herd = os.environ.get('RVW_HERD') or shutil.which('herd7')
    if not tests or not source or not herd:
        pytest.skip('set RVW_LITMUS_TESTS, RVW_HERD_SOURCE and RVW_HERD for pinned native reference checks')
    pins = json.loads(litmus.PINS.read_text())
    lib = litmus.validate_pins(Path(tests), Path(source), pins)
    allowed = {}
    for case in pins['cases']:
        output = litmus.checked([herd, '-I', str(lib), '-model', str(lib / 'riscv.cat'), str(Path(tests) / case)])
        allowed[Path(case).stem] = litmus.parse_states(output)
    zero = (('0:x7', 0), ('1:x7', 0))
    assert zero in allowed['SB']
    assert zero not in allowed['SB+fence.rw.rws']
    assert len(allowed['SB']) == 4
    assert len(allowed['SB+fence.rw.rws']) == 3
    sample = {'harts': 2, 'complete': True, 'observations': [{'state': dict(zero), 'count': 1}]}
    assert litmus.compare(allowed['SB+fence.rw.rws'], sample)['status'] == 'mismatch'
    # Exercise the project adapter protocol with a synthetic emitter, not a DUT.
    import sys
    adapter = tmp_path / 'synthetic-adapter'
    adapter.write_text(f'#!{sys.executable}\n' + '''import json, sys
from pathlib import Path
name = Path(sys.argv[1]).stem
keys = ['1:x5', '1:x7'] if name.startswith('MP') else ['0:x5', '1:x5'] if name.startswith('LB') else ['0:x7', '1:x7']
state = dict.fromkeys(keys, 1)
if name.startswith('LB+'): state = dict.fromkeys(keys, 0)
print(json.dumps({'harts': 2, 'complete': True, 'observations': [{'state': state, 'count': 1}]}))
''')
    adapter.chmod(0o755)
    command = [sys.executable, str(litmus.PINS.with_name('litmus.py')), '--tests', tests,
               '--herd-source', source, '--herd', herd, '--out', str(tmp_path / 'checked'),
               '--dut-adapter', str(adapter)]
    run = litmus.run_group(command, timeout=30, capture=True)
    assert run.returncode == 0, run.stdout
    report = json.loads(run.stdout)
    assert report['dut'] == 'consistent'
    assert all(row['dut']['exhaustive_proof'] is False for row in report['cases'])
    adapter.write_text(adapter.read_text().replace('state = dict.fromkeys(keys, 1)', 'state = dict.fromkeys(keys, 0)'))
    run = litmus.run_group(command, timeout=30, capture=True)
    assert run.returncode == 1, run.stdout
    assert json.loads(run.stdout)['dut'] == 'mismatch'


def test_recorded_blocks_and_hash(tmp_path, monkeypatch):
    import hashlib
    monkeypatch.setattr(litmus, 'validate_tests', lambda tests, pins: None)
    log = tmp_path / 'herd.logs'
    log.write_text(OUTPUT)
    pins = {'cases': {'tests/SB.litmus': 'unused'},
            'recorded': {'path': 'herd.logs', 'sha256': hashlib.sha256(log.read_bytes()).hexdigest()}}
    states = litmus.recorded_states(tmp_path, pins)
    assert states['tests/SB.litmus'] == litmus.parse_states(OUTPUT)
    log.write_text(OUTPUT.replace('1:x7=1', '1:x7=2'))
    with pytest.raises(ValueError, match='expectations differ'):
        litmus.recorded_states(tmp_path, pins)


@pytest.mark.parametrize('sample', [[], None, {'observations': 'bad'}, {'observations': [0]}])
def test_malformed_samples_inconclusive(sample):
    assert litmus.compare(litmus.parse_states(OUTPUT), sample)['status'] == 'inconclusive'


def test_empty_allowed_set_inconclusive():
    assert litmus.compare(set(), {})['status'] == 'inconclusive'


def test_recorded_official_suite(tmp_path):
    import json
    import os
    tests = os.environ.get('RVW_LITMUS_TESTS')
    if not tests:
        pytest.skip('set RVW_LITMUS_TESTS for external pinned suite')
    import sys
    result = litmus.run_group([sys.executable, str(litmus.PINS.with_name('litmus.py')),
                               '--tests', tests, '--herd', '/missing/herd7', '--out', str(tmp_path)],
                              timeout=30, capture=True)
    assert result.returncode == 0, result.stdout
    report = json.loads(result.stdout)
    assert report['reference_source'] == 'suite-recorded'
    assert report['herd_version'] is None
    assert report['dut'] == 'not_run'
    states = {Path(c['test']).stem: {litmus.canonical(s) for s in c['allowed']} for c in report['cases']}
    zero = litmus.canonical({'0:x7': 0, '1:x7': 0})
    assert zero in states['SB'] and zero not in states['SB+fence.rw.rws']


def test_native_ztso_model(tmp_path):
    import json
    import os
    import sys
    tests, source, herd = (os.environ.get(k) for k in ('RVW_LITMUS_TESTS', 'RVW_HERD_SOURCE', 'RVW_HERD'))
    if not all((tests, source, herd)):
        pytest.skip('set pinned native herd and suite paths for Ztso checks')
    command = [sys.executable, str(litmus.PINS.with_name('litmus.py')), '--tests', tests,
               '--herd-source', source, '--herd', herd, '--model', 'ztso', '--out', str(tmp_path)]
    run = litmus.run_group(command, timeout=30, capture=True)
    assert run.returncode == 0, run.stdout
    report = json.loads(run.stdout)
    assert report['memory_model'] == 'ztso' and report['model_file'] == 'riscv-tso.cat'
    assert report['implementation_support'] == 'not_verified' and report['dut'] == 'not_run'
    states = {Path(c['test']).stem: {litmus.canonical(s) for s in c['allowed']} for c in report['cases']}
    assert litmus.canonical({'0:x7': 0, '1:x7': 0}) in states['SB']
    assert litmus.canonical({'1:x5': 1, '1:x7': 0}) not in states['MP']
    assert litmus.canonical({'0:x5': 1, '1:x5': 1}) not in states['LB']
    plan = litmus.run_group([sys.executable, str(litmus.PINS.with_name('fixture.py')),
                             '--reference', str(tmp_path/'outcomes.json'), '--tests', tests,
                             '--out', str(tmp_path/'plan.json')], timeout=10, capture=True)
    assert plan.returncode == 0, (plan.stdout, plan.stderr)
    run = litmus.run_group(command+['--dut-adapter', '/missing/adapter'], timeout=30, capture=True)
    assert run.returncode == 3 and '--declared-ztso' in run.stdout


def test_no_ztso_recorded_fallback(tmp_path):
    import sys
    run = litmus.run_group([sys.executable, str(litmus.PINS.with_name('litmus.py')),
                           '--tests', str(tmp_path), '--herd', '/missing/herd7',
                           '--model', 'ztso', '--out', str(tmp_path/'out')], timeout=10, capture=True)
    assert run.returncode == 3 and 'RVWMO only' in run.stdout
