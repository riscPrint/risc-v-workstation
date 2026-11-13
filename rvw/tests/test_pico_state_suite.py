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


def test_terminal_traps_have_specific_profile_limits(monkeypatch):
    module=helper(monkeypatch)
    fence='TERMINAL_TRAP pc=80000050 insn=0000100f rs1=00000000 retirements=20'
    misalign='TERMINAL_TRAP pc=80000010 insn=00141383 rs1=80000580 retirements=4'
    assert module.simulation_outcome(0,False,fence)['status']=='unsupported'
    assert 'Zifencei' in module.simulation_outcome(0,False,fence)['reason']
    assert 'CATCH_MISALIGN' in module.simulation_outcome(0,False,misalign)['reason']
    assert module.simulation_outcome(1,False,fence)['status']=='failed'
    assert module.simulation_outcome(0,True,fence)['status']=='inconclusive'
    assert module.overall([{'status':'matched'},{'status':'unsupported'}])=='inconclusive'


def test_unknown_trap_and_missing_marker_do_not_match(monkeypatch):
    module=helper(monkeypatch)
    for text in ['','TERMINAL_TRAP pc=80000000 insn=ffffffff rs1=00000000 retirements=1']:
        assert module.simulation_outcome(0,False,text)['status']=='inconclusive'
