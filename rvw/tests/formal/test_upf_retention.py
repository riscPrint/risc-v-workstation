import json
import shutil
from pathlib import Path
import pytest
from rvw.common.proc import run_group
from rvw.formal.upf_subset import generate,parse

ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'SpinalChecks/upf/retention.upf'
BINDINGS=ROOT/'SpinalChecks/upf/retention-bindings.json'


def test_retention_import_and_bind(tmp_path):
    result=generate(SOURCE,BINDINGS,tmp_path/'out')
    assert result['status']=='generated'
    assert result['unmonitored_domains']==[]
    assert result['intent']['retention']['RET']['-retention_power_net']=='VRET'
    assert '.save(save)' in (tmp_path/'out/binds.sv').read_text()
    binding=json.loads(BINDINGS.read_text());binding.pop('retention')
    p=tmp_path/'missing.json';p.write_text(json.dumps(binding))
    with pytest.raises(ValueError,match='every retention'):
        generate(SOURCE,p,tmp_path/'bad')


@pytest.mark.parametrize('bad',['posedge','negedge','unknown'])
def test_unmodeled_controls_refused(bad):
    with pytest.raises(ValueError): parse(SOURCE.read_text().replace('save high','save '+bad))


@pytest.mark.slow
@pytest.mark.parametrize('bad',[False,True])
def test_native_retention_proof(tmp_path,bad):
    if not shutil.which('sby') or not shutil.which('yices-smt2'):
        pytest.skip('SBY and Yices required')
    generate(SOURCE,BINDINGS,tmp_path/'out')
    source=(tmp_path/'out/monitors.sv').read_text()+f'''module fixture(input clk);
reg [3:0] phase=0; always @(posedge clk) if(phase<7) phase<=phase+1;
wire reset=phase==0, power_good=phase!=2, save=phase==1, restore=phase==3, functional_use=phase>=5;
wire [7:0] state=phase==2 || phase==3 ? 99 : phase>=4 ? {41 if bad else 42} : 42;
rvw_upf_retention_RET dut(.*); endmodule
'''
    (tmp_path/'design.sv').write_text(source)
    (tmp_path/'proof.sby').write_text('''[options]
mode prove
depth 12
[engines]
smtbmc yices
[script]
read -formal design.sv
prep -top fixture
[files]
design.sv
''')
    r=run_group(['nice','-n','10','sby','-f','proof.sby'],cwd=tmp_path,capture=True,timeout=45)
    status=tmp_path/'proof/status'
    assert status.exists(),r.stdout+r.stderr
    assert status.read_text().split()[0] == ('FAIL' if bad else 'PASS'),r.stdout+r.stderr


@pytest.mark.slow
@pytest.mark.parametrize('bad',[False,True])
def test_native_supply_table(tmp_path,bad):
    if not shutil.which('sby') or not shutil.which('yices-smt2'):
        pytest.skip('SBY and Yices required')
    source=tmp_path/'power.upf'
    source.write_text('''upf_version 2.1
create_power_domain PD -elements {core}
create_pst PST -supplies {VDD VRET}
add_pst_state RUN -pst PST -state {ON ON}
add_pst_state SLEEP -pst PST -state {OFF ON}
''')
    binding=dict(schema='rvw.upf-bindings/1',top='Top',event_model='always_on_sampled',domains={'PD':{}},
        psts={'PST':dict(clk='clk',reset='reset',supplies={
            'VDD':dict(signal='vdd',states=dict(OFF=0,ON=1)),
            'VRET':dict(signal='vret',states=dict(OFF=0,ON=1))})})
    bp=tmp_path/'bindings.json';bp.write_text(json.dumps(binding))
    report=generate(source,bp,tmp_path/'out')
    assert report['status']=='generated'
    text=(tmp_path/'out/monitors.sv').read_text()+f'''module fixture(input clk);
reg reset=1; always @(posedge clk) reset<=0;
wire supply_0=0, supply_1={0 if bad else 1};
rvw_upf_pst_PST dut(.*); endmodule
'''
    (tmp_path/'design.sv').write_text(text)
    (tmp_path/'proof.sby').write_text('''[options]
mode prove
depth 8
[engines]
smtbmc yices
[script]
read -formal design.sv
prep -top fixture
[files]
design.sv
''')
    r=run_group(['nice','-n','10','sby','-f','proof.sby'],cwd=tmp_path,capture=True,timeout=45)
    status=tmp_path/'proof/status'
    assert status.exists(),r.stdout+r.stderr
    assert status.read_text().split()[0] == ('FAIL' if bad else 'PASS'),r.stdout+r.stderr
