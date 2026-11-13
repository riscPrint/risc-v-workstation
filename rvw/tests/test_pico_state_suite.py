import importlib.util
from pathlib import Path
import pytest
pytestmark=pytest.mark.fast


def helper(monkeypatch):
    path=Path(__file__).resolve().parents[2]/'examples/picorv32/formal/suite.py'
    monkeypatch.syspath_prepend(str(path.parent))
    spec=importlib.util.spec_from_file_location('pico_state_suite',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_hex_relocation_and_range(monkeypatch):
    module=helper(monkeypatch)
    assert module.relocate_hex('@20000000\n00000013\n@20000004\n00000000')=='@00000000\n00000013\n@00000004\n00000000'
    for address in ['@00000000','@20040000']:
        with pytest.raises(ValueError,match='outside'):
            module.relocate_hex(address)


def test_suite_inventory_excludes_only_m(monkeypatch,tmp_path):
    module=helper(monkeypatch)
    tests=tmp_path/'tests';tests.mkdir()
    for name in ['add','mul','jalr','fence_i','sltiu']:(tests/(name+'.S')).write_text('')
    assert [p.stem for p in module.suite_sources(tmp_path)]==['add','fence_i','jalr','sltiu']
    assert module.suite_sources(tmp_path,tests)==module.suite_sources(tmp_path)


def test_no_unearned_suite_match(monkeypatch):
    module=helper(monkeypatch)
    assert module.overall([])=='inconclusive'
    assert module.overall([{'status':'matched'},{'status':'inconclusive'}])=='inconclusive'
    assert module.overall([{'status':'matched'},{'status':'failed'}])=='failed'
    assert module.overall([{'status':'matched'}])=='matched'
