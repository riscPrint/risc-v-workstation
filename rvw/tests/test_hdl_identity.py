import json
import pytest

from rvw.init.hdl import scaffold_hdl
from rvw.init.hdl_identity import collect
from rvw.regress.adapter_capture import accept, claim_error

pytestmark = pytest.mark.fast


def test_hdl_identity_tracks_build_inputs(tmp_path, monkeypatch):
    (tmp_path / 'top.sv').write_text('module top; endmodule\n')
    scaffold_hdl(tmp_path, hdl='sv', top='top', isa='rv32i', name='test')
    monkeypatch.setattr('rvw.init.hdl_identity.native_identity',
                        lambda: dict(sha256='1' * 64, cache_enabled=True))
    manifest = tmp_path / 'rvw/hdl.json'
    source = dict(core_repo=str(tmp_path), core_rev='abc', core_rev_full='abc', core_dirty=False)
    monkeypatch.setenv('RVW_CAPTURE_SOURCE', json.dumps(source))
    preprocess = lambda args: b'elaborated includes'
    first, command = collect(manifest, preprocess=preprocess)
    assert accept(json.dumps(first), source) == first
    assert '--top-module' in command
    assert str(tmp_path / 'rvw/sim/harness.cpp') in command
    assert first['result_claims']['rtl_sha256']
    assert claim_error(first['result_claims'], {})
    (tmp_path / 'rvw/sim/harness.cpp').write_text('// changed harness')
    second, _ = collect(manifest, preprocess=preprocess)
    assert first['result_claims'] != second['result_claims']
    third, _ = collect(manifest, preprocess=lambda args: b'changed include')
    assert second['result_claims']['rtl_sha256'] != third['result_claims']['rtl_sha256']
    spec = json.loads(manifest.read_text())
    spec['defines'] = ['FEATURE=1']
    spec['include_dirs'] = ['include']
    spec['verilator_flags'].append('--trace')
    manifest.write_text(json.dumps(spec))
    fourth, command = collect(manifest, preprocess=preprocess)
    assert fourth['result_claims'] != third['result_claims']
    assert '-DFEATURE=1' in command
    assert '-I' + str(tmp_path / 'include') in command
    assert '--trace' in command
