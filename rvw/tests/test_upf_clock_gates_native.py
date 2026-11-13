import json
import shutil
import subprocess

import pytest
from rvw.formal.upf_subset import generate

pytestmark=pytest.mark.slow


@pytest.mark.parametrize('fault',['none','enable_phase','edge_while_off','late_wakeup'])
def test_generated_clock_gate_native(tmp_path,fault):
    iverilog=shutil.which('iverilog');vvp=shutil.which('vvp')
    if not iverilog or not vvp:pytest.skip('Icarus is required')
    source=tmp_path/'intent.upf';source.write_text('upf_version 2.1\ncreate_power_domain core -elements {u_core}\n')
    ports=('clk','reset','enable','source_low','clock_edge','work_pending','wakeup')
    gate=dict(domain='core',wake_cycles=3,**{p:p for p in ports})
    binding=tmp_path/'bindings.json';binding.write_text(json.dumps(dict(schema='rvw.upf-bindings/1',top='top',event_model='always_on_sampled',domains={'core':{}},clock_gates={'core':gate})))
    generate(source,binding,tmp_path/'generated')
    phase='0' if fault=='enable_phase' else '1'
    edge='1' if fault=='edge_while_off' else '0'
    enable='0' if fault=='late_wakeup' else '1'
    tb=tmp_path/'tb.sv';tb.write_text(f'''module top;
reg clk=0,reset=1,enable=0,source_low=1,clock_edge=0,work_pending=0,wakeup=0;
always #5 clk=~clk;
rvw_upf_clock_gate_core dut(.*);
initial begin
 #12 reset=0;
 #8 wakeup=1;clock_edge={edge};
 #10 wakeup=0;enable={enable};clock_edge={enable};source_low={phase};
 #10 clock_edge=0;
 #50 $display("EXERCISED");$finish;
end
endmodule
''')
    binary=tmp_path/'sim'
    compile=subprocess.run([iverilog,'-g2012','-s','top','-o',str(binary),str(tmp_path/'generated/monitors.sv'),str(tb)],capture_output=True,text=True,timeout=20)
    assert compile.returncode==0,compile.stdout+compile.stderr
    run=subprocess.run([vvp,str(binary)],capture_output=True,text=True,timeout=20)
    log=run.stdout+run.stderr
    assert run.returncode==0 and 'EXERCISED' in log
    assert ('ERROR' in log)==(fault!='none'),log
