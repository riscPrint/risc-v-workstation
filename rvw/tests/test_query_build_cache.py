from pathlib import Path
import pytest
from rvw.query import build_cache
from rvw.query.hdl import build_hdl

pytestmark = pytest.mark.fast


def test_cache_reuse_and_invalidation(tmp_path, monkeypatch):
    src = tmp_path / 'src'
    src.mkdir()
    source = src / 'top.v'
    source.write_text('module top; endmodule')
    tool = tmp_path / 'yosys'
    tool.write_text('tool version 1')
    monkeypatch.setattr(build_cache.shutil, 'which', lambda name: str(tool))
    calls = []
    def builder(sources, top, out, **options):
        calls.append(top)
        Path(out).write_bytes(b'captured database')
        return {'db': str(out), 'top': top, 'frontend': 'yosys-verilog'}
    cache, out = tmp_path / 'cache', tmp_path / 'design.db'
    def run(**options):
        return build_cache.cached_build(builder, [source], 'top', out, cache, options)
    a = run()
    assert a['cache']['status'] == 'rebuilt'
    out.unlink()
    assert run()['cache']['status'] == 'hit' and len(calls) == 1
    assert out.read_bytes() == b'captured database'
    source.write_text('module top; wire changed; endmodule')
    assert run()['cache']['status'] == 'rebuilt' and len(calls) == 2
    tool.write_text('tool version 2')
    assert run()['cache']['status'] == 'rebuilt' and len(calls) == 3
    assert run(parameters=['WIDTH=4'])['cache']['status'] == 'rebuilt'
    assert run(parameters=['WIDTH=4'])['cache']['status'] == 'hit'
    entry = cache / (run(parameters=['WIDTH=4'])['cache']['key'] + '.db')
    entry.write_bytes(b'corrupt')
    assert run(parameters=['WIDTH=4'])['cache']['status'] == 'rebuilt'
    with pytest.raises(ValueError, match='alias'):
        build_hdl([source], 'top', source, cache_dir=cache)


def test_include_hash_and_failed_build(tmp_path, monkeypatch):
    src = tmp_path / 'src'
    src.mkdir()
    source, include = src / 'top.sv', src / 'defs.svh'
    source.write_text('`include "defs.svh"')
    include.write_text('`define WIDTH 4')
    tool = tmp_path / 'yosys'
    tool.write_text('fake')
    monkeypatch.setattr(build_cache.shutil, 'which', lambda name: str(tool))
    monkeypatch.setattr('rvw.query.hdl._slang_plugin', lambda *a: tool)
    a = build_cache.identity([source], 'top', {'frontend': 'slang'})
    include.write_text('`define WIDTH 8')
    assert build_cache.identity([source], 'top', {'frontend': 'slang'}) != a
    def failed(*a, **kw):
        raise ValueError('native build failed')
    out = tmp_path / 'design.db'
    out.write_bytes(b'old database')
    with pytest.raises(ValueError, match='native build failed'):
        build_cache.cached_build(failed, [source], 'top', out, tmp_path / 'cache', {})
    assert out.read_bytes() == b'old database'
