from argparse import Namespace
import json
import shutil
import threading
import time

import pytest

from rvw.formal import regression
from rvw.results import validate


def test_task_selection():
    job = '[tasks]\na common\nb\n[options]\nmode bmc\na: depth 3\nb: depth 5\n~common: wait on\n'
    a = regression.task_config(job, 'a')
    assert 'depth 3' in a and 'depth 5' not in a and 'wait on' not in a
    b = regression.task_config(job, 'b')
    assert 'depth 5' in b and 'wait on' in b
    with pytest.raises(ValueError, match='unsupported:sby_task'):
        regression.task_config(job)
    with pytest.raises(ValueError, match='unsupported:sby_python'):
        regression.task_config('--pycode-begin--')


def fixture(tmp_path):
    (tmp_path / 'm.sv').write_text('module m(input clk); always @(posedge clk) assert(1); endmodule')
    (tmp_path / 'm.sby').write_text('''[tasks]
a
b
[options]
mode bmc
depth 4
[engines]
smtbmc yices
[script]
read -formal m.sv
prep -top m
[files]
m.sv
''')
    manifest = tmp_path / 'suite.toml'
    manifest.write_text('\n'.join(f'[[property]]\nid="{i}"\nsby="m.sby"\ntop="m"\ntask="{i}"' for i in ['a', 'b']))
    return Namespace(manifest=str(manifest), out=str(tmp_path / 'out'), jobs=2, timeout=20, json=False)


def test_parallel_and_junit(tmp_path, monkeypatch):
    args = fixture(tmp_path)
    class Tools:
        def __init__(self, *args):
            pass
    monkeypatch.setattr(regression, 'Toolchain', Tools)
    lock = threading.Lock()
    active = peak = 0
    def observe(prop, *args):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(.05)
        with lock:
            active -= 1
        return {'id': prop['id'], 'status': 'pass', 'formal_status': 'bounded-pass',
                'depth': 4, 'seed': None, 'signature': None, 'wall_s': .05, 'run': None,
                'inconclusive': 'conditional observation'}
    monkeypatch.setattr(regression, 'observe', observe)
    assert regression.run(args) == 1
    data = json.loads((tmp_path / 'out/results.json').read_text())
    assert not validate(data)
    assert peak == min(2, regression.os.cpu_count() or 1)
    assert [t['id'] for t in data['tests']] == ['a', 'b']
    xml = (tmp_path / 'out/junit.xml').read_text()
    assert 'conditional observation' in xml and '<error' in xml


def test_native_regression(tmp_path):
    if not shutil.which('sby') or not shutil.which('yices-smt2'):
        pytest.skip('SBY and Yices required')
    args = fixture(tmp_path)
    assert regression.run(args) == 1
    data = json.loads((tmp_path / 'out/results.json').read_text())
    assert [p['formal_status'] for p in data['tests']] == ['bounded-pass'] * 2
    assert all(p['depth'] == 4 for p in data['tests'])


def test_unsupported_is_recorded(tmp_path):
    args = fixture(tmp_path)
    path = tmp_path / 'm.sby'
    path.write_text(path.read_text().replace('mode bmc', 'mode live'))
    assert regression.run(args) == 1
    data = json.loads((tmp_path / 'out/results.json').read_text())
    assert all(p['formal_status'] == 'unsupported' for p in data['tests'])


@pytest.mark.parametrize('status', ['timeout', 'unknown'])
def test_missing_model_keeps_unresolved_status(tmp_path, monkeypatch, status):
    directory = tmp_path / 'prop'
    directory.mkdir()
    job = directory / 'job.sby'
    job.write_text('')
    class Tools:
        env = {}
        def command(self, argv):
            return argv
        def verify(self):
            pass
    monkeypatch.setattr(regression, 'execute', lambda *a, **kw: (124, .1))
    monkeypatch.setattr(regression.common, 'final_status', lambda *a: status)
    result = regression.observe({'id': 'prop', 'top': 'm'}, directory, job, 'bmc', Tools(), 1, 8)
    assert result['formal_status'] == status
