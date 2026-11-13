"""UVM severity summaries must not permit a successful result after an error."""
import pytest
from rvw.sim import uvm
from rvw.uvm.flow import evidence

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('severity', ['ERROR', 'FATAL'])
@pytest.mark.parametrize('prefix', ['', '  ', '\t'])
@pytest.mark.parametrize('count', [0, 1])
def test_indented_severity_summary(severity, prefix, count):
    summary = f'{prefix}UVM_{severity} : {count}\n'
    log = '\n'.join(f'RVW_UVM_PASS {name}' for name in uvm.FEATURES)
    assert uvm.evidence(log + '\nRVW_UVM_DONE\n' + summary, 0, False) == (count == 0)
    status, _ = evidence('RVW_UVM_DONE smoke checks=1\n' + summary, 'smoke', 0, False)
    assert status == ('pass' if count == 0 else 'fail')
