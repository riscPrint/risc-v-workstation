import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from rvw.results.schema import load_results
from rvw.sim.cocotb import entries, load, run


def manifest(tmp_path, **overrides):
    (tmp_path / 'dut.v').write_text('module dut; endmodule')
    d = dict(schema='rvw.cocotb/1', name='unit', backend='icarus', top='dut',
             sources=['dut.v'], test_module='test_dut')
    d.update(overrides)
    p = tmp_path / 'test.json'
    p.write_text(json.dumps(d))
    return p


def test_refuse_before_spawn(tmp_path, monkeypatch):
    monkeypatch.setattr('rvw.sim.cocotb.run_group', lambda *a, **k: pytest.fail('spawned'))
    with pytest.raises(ValueError, match='xz_values'):
        run(manifest(tmp_path, backend='verilator', requires=['xz_values']), tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


@pytest.mark.parametrize('xml,code,status', [
    ('<testsuite><testcase name="ok"/></testsuite>', 0, 'pass'),
    ('<testsuite><testcase name="bad"><failure/></testcase></testsuite>', 1, 'fail'),
    ('<testsuite><testcase name="skip"><skipped/></testcase></testsuite>', 0, 'error'),
    ('<testsuite/>', 0, 'error'),
    ('<testsuite><testcase name="ok"/></testsuite>', 1, 'error'),
    ('broken', 0, 'error'),
    ('<testsuite><testcase name="ok" time="nan"/></testsuite>', 0, 'error'),
    ('<testsuite><testcase name="ok"/><testcase name="ok"/></testsuite>', 0, 'error'),
])
def test_results(tmp_path, monkeypatch, xml, code, status):
    def worker(argv, **kwargs):
        (Path(argv[-2]) / 'cocotb.xml').write_text(xml)
        return SimpleNamespace(returncode=code, timed_out=False)
    monkeypatch.setattr('rvw.sim.cocotb.run_group', worker)
    out = tmp_path / 'out'
    report = run(manifest(tmp_path), out)
    assert report['tests'][0]['status'] == status
    assert load_results(out).tests[0].status == status
    if status == 'pass':
        from rvw.regress.compare import compare
        suite = load_results(out)
        assert compare([suite], [suite]).verdict == 'inconclusive'
    with pytest.raises(FileExistsError):
        run(tmp_path / 'test.json', out)


def test_timeout_cannot_pass(tmp_path, monkeypatch):
    def worker(argv, **kwargs):
        (Path(argv[-2]) / 'cocotb.xml').write_text('<testsuite><testcase name="ok"/></testsuite>')
        return SimpleNamespace(returncode=124, timed_out=True)
    monkeypatch.setattr('rvw.sim.cocotb.run_group', worker)
    report = run(manifest(tmp_path), tmp_path / 'out')
    assert report['tests'][0]['status'] == 'error'


@pytest.mark.parametrize('overrides', [dict(requires=['bogus']), dict(backend='other'),
    dict(reset=dict(signal='rst', active=1, cycles=1)),
    dict(clock=dict(signal='clk', period_ns=0)), dict(sources=[])])
def test_bad_manifest(tmp_path, overrides):
    with pytest.raises(ValueError):
        load(manifest(tmp_path, **overrides))


def test_changed_source_cannot_pass(tmp_path, monkeypatch):
    def worker(argv, **kwargs):
        (Path(argv[-2]) / 'cocotb.xml').write_text('<testsuite><testcase name="ok"/></testsuite>')
        (tmp_path / 'dut.v').write_text('changed')
        return SimpleNamespace(returncode=0, timed_out=False)
    monkeypatch.setattr('rvw.sim.cocotb.run_group', worker)
    result = run(manifest(tmp_path), tmp_path / 'out')
    assert result['tests'][0]['status'] == 'error'
    assert 'inputs changed' in result['tests'][0]['inconclusive']


def test_backend_non_string(tmp_path):
    with pytest.raises(ValueError, match='unsupported backend'):
        load(manifest(tmp_path, backend=[]))
