import json
from rvw.uvm.qualification import generate
import pytest
pytestmark=pytest.mark.fast


def test_missing_and_failed_tests_stay_unqualified(tmp_path):
    cpu=tmp_path/'results.json'
    cpu.write_text(json.dumps(dict(schema='rvw.results/1',suite='cpu',core='cpu',config='c',run_id='r',
        created='2026-11-13T00:00:00Z',source={},tests=[dict(id='spike_retirements',seed=1,status='fail',signature='uvm:fail')],engine='Verilator test')))
    probes=tmp_path/'probes.json';probes.write_text(json.dumps(dict(engine='Verilator test',probes=[
        dict(feature='transition',status='runtime_gap',ignored_feature_warning=True)])))
    out=tmp_path/'matrix.md';generate(cpu,probes,out)
    text=out.read_text()
    assert '| spike_retirements | 1 | not established |' in text
    assert '| spike_csr_fault_detection | 0 | not established |' in text
    assert 'runtime_gap; ignored-feature warning' in text
    assert 'pyuvm observed bins' in text
