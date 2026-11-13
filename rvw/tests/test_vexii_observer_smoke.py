"""Keep incomplete directed observer runs out of positive evidence."""
import importlib.util
from pathlib import Path
import pytest
pytestmark=pytest.mark.fast
path=Path(__file__).resolve().parents[2]/'examples/vexiiriscv/formal/observer_smoke.py'
spec=importlib.util.spec_from_file_location('vexii_observer_smoke',path)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def test_success_marker_requires_successful_process():
    assert m.verdict(0,'OBSERVER_SMOKE_PASS records=18')=='matched'
    assert m.verdict(1,'OBSERVER_SMOKE_PASS records=18')!='matched'
    assert m.verdict(0,'retired 18')=='inconclusive'


def test_negative_control_must_reach_the_store_check():
    assert m.verdict(1,'FATAL: store mismatch',negative=True)=='detected'
    assert m.verdict(1,'compile failed',negative=True)=='inconclusive'
    assert m.verdict(0,'store mismatch',negative=True)=='inconclusive'


def test_actual_mismatch_is_failed_evidence():
    assert m.verdict(1,'FATAL: trap mismatch')=='failed'


def test_assertion_diagnostic_overrides_a_late_success_marker():
    assert m.verdict(0,'FAILURE: memory tag\nOBSERVER_SMOKE_PASS records=18')=='failed'
