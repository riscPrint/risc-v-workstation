import json
import pytest
from rvw.workloads.comparison import compare, render
pytestmark = pytest.mark.fast


def table(path, cycles, samples=2):
    row = {'program': 'kernel', 'status': 'pass', 'instructions': 10,
           'cycles': cycles, 'ipc': 10/cycles, 'elf_sha256': 'elf',
           'topdown': {'unit': 'commit_slots', 'fractions': {'retiring': 10/cycles}},
           'samples': [{'status': 'pass', 'instructions': 10, 'cycles': cycles} for _ in range(samples)]}
    path.write_text(json.dumps({'schema': 'rvw.rtl-bench/1', 'workloads': [row]}))
    return path


def test_compare_and_noise(tmp_path):
    a = table(tmp_path / 'a', 20)
    b = table(tmp_path / 'b', 10)
    r = compare(a,b)
    assert r['status'] == 'compared'
    assert 'retiring delta (pp)' in render(r)
    assert '50.0' in render(r)
    assert r['workloads'][0]['ipc_delta_pct'] == 100
    assert r['workloads'][0]['topdown_delta'] == {'retiring': .5}
    table(b, 10, samples=1)
    assert compare(a,b)['status'] == 'inconclusive'
    data = json.loads(a.read_text())
    data['workloads'][0]['samples'][1]['cycles'] += 1
    a.write_text(json.dumps(data))
    table(b, 10)
    assert compare(a,b)['status'] == 'inconclusive'


def test_missing_failed_and_changed_program(tmp_path):
    a = table(tmp_path / 'a',20)
    b = table(tmp_path / 'b',10)
    data=json.loads(b.read_text()); data['workloads'][0]['instructions']=11
    b.write_text(json.dumps(data))
    assert 'counts differ' in compare(a,b)['workloads'][0]['reason']
    data['workloads'][0]['status']='fail'; b.write_text(json.dumps(data))
    assert 'did not pass' in compare(a,b)['workloads'][0]['reason']
    data['workloads']=[]; b.write_text(json.dumps(data))
    assert 'missing' in compare(a,b)['workloads'][0]['reason']
