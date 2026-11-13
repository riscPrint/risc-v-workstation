"""A warm launch must invalidate changed source, bytecode and libraries."""
import runpy
from pathlib import Path
import pytest

pytestmark = pytest.mark.fast
M = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'examples/vexiiriscv/rvw/classpath-cache.py'))


def test_cache_rejects_source_and_runtime_changes(tmp_path):
    src, classes = tmp_path / 'src', tmp_path / 'classes'
    src.mkdir(); classes.mkdir()
    source, bytecode = src / 'Core.scala', classes / 'Core.class'
    source.write_text('original'); bytecode.write_bytes(b'original bytecode')
    cache = tmp_path / 'cp.json'
    def save():
        M['save'](cache, [src], M['sources']([src]), str(classes))
    save()
    assert M['load'](cache, [src]) == str(classes)
    source.write_text('changed')
    with pytest.raises(ValueError): M['load'](cache, [src])
    save(); bytecode.write_bytes(b'changed bytecode')
    with pytest.raises(ValueError): M['load'](cache, [src])
    save(); (src / 'New.scala').write_text('new untracked source')
    with pytest.raises(ValueError): M['load'](cache, [src])


def test_compilation_source_drift_and_removed_jar(tmp_path):
    source, jar = tmp_path / 'Core.scala', tmp_path / 'lib.jar'
    source.write_text('original'); jar.write_bytes(b'jar')
    before = M['sources']([tmp_path])
    source.write_text('changed')
    with pytest.raises(ValueError, match='during compilation'):
        M['save'](tmp_path / 'cp.json', [tmp_path], before, str(jar))
    M['save'](tmp_path / 'cp.json', [tmp_path], M['sources']([tmp_path]), str(jar))
    jar.unlink()
    with pytest.raises(ValueError): M['load'](tmp_path / 'cp.json', [tmp_path])
