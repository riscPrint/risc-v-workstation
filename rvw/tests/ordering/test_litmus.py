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
keys = ['1:x5', '1:x7'] if name == 'MP' else ['0:x5', '1:x5'] if name == 'LB' else ['0:x7', '1:x7']
state = dict.fromkeys(keys, 1)
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
