import json
from pathlib import Path
import shutil
import sys
import pytest
from rvw.sec.isolation import run
pytestmark=pytest.mark.slow


@pytest.mark.parametrize('leak',[True,False])
def test_private_state_boundary(tmp_path,leak):
    if not shutil.which('verilator'):pytest.skip('Verilator required')
    p=dict(isolation_kind='register-state',boundary='privileged to public',
           policy={'cleanup':'clear private history'},contract='sandboxing',contract_start_pc=0x100,
           clauses=['pc'],observations=['cycles'],public={'leak':leak,'isolation':True},
           secrets=[0,1],program=['nop'],minimize_runs=0,
           adapter_command=[sys.executable,str(Path(__file__).parent/'fixtures/sec/adapter.py'),'{request}','{out}'])
    (tmp_path/'plan.json').write_text(json.dumps(p))
    result=run(tmp_path/'plan.json',tmp_path/'out')
    assert result['status']==('violation' if leak else 'no_leak_observed'),result
