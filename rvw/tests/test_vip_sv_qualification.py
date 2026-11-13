"""Native matrix checks require positive and specific negative evidence."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('sv_qualification', ROOT/'Uvm/vip/qualification/run.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_each_runtime_fixture_has_a_good_and_bad_case():
    for source in (ROOT/'Uvm/vip').glob('*/smoke.py'):
        if not (source.parent/'test.sv').exists():
            continue
        matrix = module.cases(source)
        assert matrix[0][0] == ''
        assert any(diagnostic != matrix[0][1] for _, diagnostic in matrix)


def test_empty_crash_timeout_and_unrelated_fatal_do_not_qualify():
    ok = SimpleNamespace(returncode=0, timed_out=False)
    bad = SimpleNamespace(returncode=-6, timed_out=False)
    timeout = SimpleNamespace(returncode=-15, timed_out=True)
    assert not module.checked('', ok, 'DONE', 'DONE', False)
    assert not module.checked('DONE\nDONE', ok, 'DONE', 'DONE', False)
    assert not module.checked('UVM_FATAL [OTHER]', bad, 'DONE', 'DATA', True)
    assert not module.checked('UVM_FATAL [DATA]', timeout, 'DONE', 'DATA', True)
    assert not module.checked('DONE\nUVM_ERROR [DATA]', ok, 'DONE', 'DONE', False)
    assert module.checked('DONE\nUVM_ERROR :    0\nUVM_FATAL :    0', ok, 'DONE', 'DONE', False)
    assert module.checked('UVM_FATAL [DATA] mismatch', bad, 'DONE', 'DATA', True)
    assert module.checked('%Fatal: Assertion failed: DATA', bad, 'DONE', 'DATA', True)
    assert not module.checked('DONE\nUVM_FATAL [DATA]', bad, 'DONE', 'DATA', True)


def test_component_runtime_fatals_use_stop_action():
    for source in (ROOT/'Uvm/vip').glob('*/test.sv'):
        if (source.parent/'smoke.py').exists():
            assert 'UVM_DISPLAY|UVM_STOP' in source.read_text(), source


def test_corruption_diagnostic_requires_passing_baseline_for_qualification():
    runs=[dict(fault='',checked=False),dict(fault='buggy',checked=True)]
    assert module.assessment(runs)==dict(runs_good=False,catches_bad_dut=False)
    runs[0]['checked']=True
    assert module.assessment(runs)==dict(runs_good=True,catches_bad_dut=True)
    assert module.assessment([])==dict(runs_good=False,catches_bad_dut=False)
