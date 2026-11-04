import hashlib
import json
from types import SimpleNamespace
import pytest
from rvw.regress.vector import check


def fixture(tmp_path, monkeypatch, result):
    from rvw.cosim import cli
    from rvw import results
    from rvw.cosim.platform import Platform
    elfs = tmp_path / 'elfs'
    elfs.mkdir()
    elf = elfs / 'vadd'
    elf.write_bytes(b'\x7fELFtest')
    digest = hashlib.sha256(elf.read_bytes()).hexdigest()
    run = SimpleNamespace(elf_sha256=digest, why_inconclusive=None, status='pass',
                          path=tmp_path, artifacts={'rvfi_trace': 'rvfi.jsonl'})
    (tmp_path/'result.json').write_text('{}')
    monkeypatch.setattr(results, 'load_run', lambda _: run)
    monkeypatch.setattr(Platform, 'load', lambda *a: SimpleNamespace(isa='rv64imafdcv_zicsr'))
    monkeypatch.setattr(cli, 'calculate', lambda args: (result, 0))
    return elfs, run


def good():
    return dict(status='match', instructions=1, trace_complete=True,
                end_status='pass', synchronized=0, state_coverage={'vector': {'vlen':128,'elen':64}})


@pytest.mark.parametrize('changes', [{}, {'trace_complete':False}, {'end_status':'halt'},
    {'synchronized':1}, {'instructions':0}, {'state_coverage':{}}, {'status':'mismatch'}, {'status':'error'}])
def test_suite_requires_complete_vector_evidence(tmp_path, monkeypatch, changes):
    result = good() | changes
    elfs, run = fixture(tmp_path, monkeypatch, result)
    out = check(elfs, tmp_path, tmp_path/'platform.json')
    expected = 'pass' if not changes else 'fail' if changes.get('status') == 'mismatch' else 'inconclusive'
    assert out['status'] == expected


def test_missing_and_failed_c1(tmp_path, monkeypatch):
    elfs, run = fixture(tmp_path, monkeypatch, good())
    run.artifacts = {}
    assert check(elfs, tmp_path, tmp_path/'p.json')['status'] == 'inconclusive'
    run.status = 'fail'
    assert check(elfs, tmp_path, tmp_path/'p.json')['status'] == 'fail'


def test_requires_v(tmp_path, monkeypatch):
    from rvw.cosim.platform import Platform
    elfs, _ = fixture(tmp_path, monkeypatch, good())
    monkeypatch.setattr(Platform, 'load', lambda *a: SimpleNamespace(isa='rv64imac'))
    with pytest.raises(ValueError, match='declaring V'):
        check(elfs, tmp_path, tmp_path/'p.json')
