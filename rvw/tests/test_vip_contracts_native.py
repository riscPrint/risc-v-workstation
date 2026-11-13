"""Opt-in real RTL controls for the four semantic protocol profiles."""
import os
from pathlib import Path
import sys
import json
import pytest
from rvw.common.proc import run_group

pytestmark=pytest.mark.skipif(os.environ.get('RVW_UVM_CONTRACTS_NATIVE')!='1',reason='set RVW_UVM_CONTRACTS_NATIVE=1 for native Icarus controls')
ROOT=Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('protocol',['pcie','ethernet','dram','coherent'])
def test_real_good_and_corrupt_semantic_endpoints(tmp_path,protocol):
    out=tmp_path/protocol
    env=dict(os.environ)
    # Parse expected failing XML ourselves; disable cocotb runner's pytest exit.
    env.pop('PYTEST_CURRENT_TEST',None)
    result=run_group([sys.executable,str(ROOT/'Uvm/vip/rtl/contracts_smoke.py'),
        '--protocol',protocol,'--out',str(out)],cwd=ROOT,env=env,capture=True,timeout=60)
    assert not result.timed_out and result.returncode==0,result.stdout+result.stderr
    report=json.loads((out/'results.json').read_text())
    assert report['runs']==[dict(bad=False,checked=True,results=str(out/'0/results.xml')),
                            dict(bad=True,checked=True,results=str(out/'1/results.xml'))]
