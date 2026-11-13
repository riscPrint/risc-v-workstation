import json
import shutil
import subprocess
from pathlib import Path
import pytest
from rvw.formal.upf_subset import parse,generate,render

ROOT=Path(__file__).resolve().parents[3]
SOURCE=(ROOT/'SpinalChecks/upf/isolation.upf').read_text()


def test_literal_subset_and_generation(tmp_path):
    obj=parse(SOURCE)
    assert obj['domains']['PD']['elements']==['core']
    assert obj['isolation']['ISO']['-clamp_value']=='0'
    result=generate(ROOT/'SpinalChecks/upf/isolation.upf',ROOT/'SpinalChecks/upf/bindings.json',tmp_path/'out')
    assert result['status']=='generated'
    assert result['unmonitored_domains']==[]
    assert '.isolate(iso)' in (tmp_path/'out/binds.sv').read_text()
    assert len(result['source_sha256'])==64


@pytest.mark.parametrize('text',[
    'create_power_domain PD -elements {core}',
    'upf_version 3.0\ncreate_power_domain PD -elements {core}',
    SOURCE+'\nset_retention R -domain PD',
    SOURCE+'\nsource more.upf',
    SOURCE.replace('{core}','{$core}'),
    SOURCE.replace('{core}','{[exec true]}'),
    SOURCE.replace('{core}','{core}; puts ignored'),
    SOURCE.replace('outputs','inputs'),
    SOURCE.replace('-clamp_value 0','-clamp_value z'),
    SOURCE.replace('-isolation_sense high','-isolation_sense invalid'),
    SOURCE.replace('-elements {core}','-elements {core} -include_scope yes'),
    SOURCE+'\ncreate_power_domain PD -elements {again}',
])
def test_unrepresented_semantics_refused(text):
    with pytest.raises(ValueError): parse(text)


@pytest.mark.parametrize('sense',['high','low'])
@pytest.mark.parametrize('clamp',[0,1])
@pytest.mark.parametrize('bad',['none','clamp','late_isolation','valid_off','invalid_use'])
def test_native_clamp_and_power_order(tmp_path,sense,clamp,bad):
    if not shutil.which('iverilog') or not shutil.which('vvp'): pytest.skip('Icarus is not installed')
    (tmp_path/'m.sv').write_text(render(8,clamp,sense))
    on=1 if sense=='high' else 0
    off=1-on
    value=255 if clamp else 0
    first = off if bad=='late_isolation' else on
    valid_off = 1 if bad=='valid_off' else 0
    tb=f'''module tb;
reg clk=0; always #5 clk=~clk;
reg reset=1,power_good=1,isolate={off},output_valid=1,consumer_use=0;
reg [7:0] value=7;
rvw_upf_isolation dut(.*);
initial begin #11; reset=0; isolate={first}; value={value};
#10; power_good=0; isolate={on}; output_valid={valid_off}; value={value ^ 1 if bad=='clamp' else value};
#10; power_good=1; #10; isolate={off}; output_valid={0 if bad=='invalid_use' else 1}; consumer_use={1 if bad=='invalid_use' else 0}; value=9;
#10; $finish; end endmodule'''
    (tmp_path/'tb.sv').write_text(tb)
    build=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(tmp_path/'sim'),str(tmp_path/'m.sv'),str(tmp_path/'tb.sv')],capture_output=True,text=True,timeout=15)
    assert build.returncode==0,build.stderr
    run=subprocess.run(['vvp',str(tmp_path/'sim')],capture_output=True,text=True,timeout=15)
    assert ('ERROR:' in run.stdout)==(bad!='none')
