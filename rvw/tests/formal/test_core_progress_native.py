"""Check finite liveness accounting without inferring eventuality from a prefix."""
import importlib.util
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.parametrize('response,passed,pending', [(0,0,1),(1,1,0)])
def test_native_pending_and_completed_requests(tmp_path,response,passed,pending):
    if not all(shutil.which(t) for t in ('iverilog','vvp')):
        pytest.skip('Icarus required')
    path = Path(__file__).resolve().parents[3]/'examples/vexriscv/rvw/core-progress.py'
    spec = importlib.util.spec_from_file_location('progress',path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rtl, props = module.instrument('module m(input clk,req,ack); endmodule',
        'p: assert property (@(posedge clk) req |-> s_eventually ack); // rvw-source: Test.scala:12')
    assert props[0]['source']==dict(file='Test.scala',line=12)
    source=tmp_path/'m.sv'
    source.write_text(rtl + '\nmodule tb; reg clk=0,req=1,ack=0; m d(clk,req,ack); initial begin '
        '#1; clk=1; #1; clk=0; req=0; ack='+str(response)+'; #1; clk=1; #1; clk=0; $finish; end endmodule')
    compiled = subprocess.run(['nice','-n','10','iverilog','-g2012','-s','tb','-o',str(tmp_path/'sim'),str(source)],
                   capture_output=True,text=True,timeout=30)
    assert compiled.returncode == 0, compiled.stderr
    result=subprocess.run(['nice','-n','10','vvp',str(tmp_path/'sim')],
                          capture_output=True,text=True,check=True,timeout=30)
    assert f'RVW_COUNT rvw_live_sim_0 pass {passed}' in result.stdout
    assert 'RVW_COUNT rvw_live_sim_0 activated 1' in result.stdout
    assert f'RVW_PENDING rvw_live_sim_0 {pending}' in result.stdout
