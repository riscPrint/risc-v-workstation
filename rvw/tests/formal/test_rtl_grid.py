import hashlib
from pathlib import Path
import pytest
from rvw.formal import rtl_grid


def test_bundle_and_local_split(tmp_path, monkeypatch):
    source = tmp_path / 'p.sv'
    source.write_text('module top; endmodule')
    cases = [{'id': n, 'top': 'top', 'sources': [{'path': source.name,
             'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}]} for n in ('a', 'b')]
    bundled = rtl_grid.bundle({'cases': cases}, tmp_path)
    assert len(bundled['blobs']) == 1
    def race(case, root, out, **kw):
        assert (root / case['sources'][0]['path']).read_bytes() == source.read_bytes()
        return {'status': 'pass' if case['id'] == 'a' else 'fail', 'proof_kind': 'unbounded', 'winner': None}
    monkeypatch.setattr(rtl_grid, 'race', race)
    report = rtl_grid.local(bundled, tmp_path / 'grid', workers=2)
    assert report['status'] == 'fail'
    assert [r['property'] for r in report['rows']] == ['a', 'b']
    cases[0]['sources'][0]['sha256'] = '0' * 64
    with pytest.raises(ValueError, match='hash mismatch'):
        rtl_grid.bundle({'cases': cases}, tmp_path)
