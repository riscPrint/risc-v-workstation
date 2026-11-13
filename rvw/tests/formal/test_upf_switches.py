import shutil
import pytest
from rvw.common.proc import run_group
from rvw.formal.upf_switches import parse,generate

OPTS={'-domain':'PD','-input_supply_port':'VIN VDD','-output_supply_port':'VOUT VDD_SW',
      '-control_port':'CTL gate','-on_state':'ON VIN CTL'}
BIND={'clk':'clk','reset':'reset','input_good':'input_good','output_good':'output_good','settle_cycles':2}


def test_literal_switch():
    item=parse('SW',OPTS,{'PD':{}})
    sources,binds=generate({'SW':item},{'SW':BIND},'Top')
    assert '.control(gate)' in binds[0]
    assert 'age>=1' in sources[0]
    for expression in ('A && B','UNKNOWN','!!CTL'):
        with pytest.raises(ValueError):
            parse('SW',dict(OPTS,**{'-on_state':'ON VIN '+expression}),{'PD':{}})
    with pytest.raises(ValueError): generate({'SW':item},{},'Top')


@pytest.mark.slow
@pytest.mark.parametrize('bad',[False,True])
def test_native_power_switch(tmp_path,bad):
    if not shutil.which('sby') or not shutil.which('yices-smt2'):
        pytest.skip('SBY and Yices required')
    item=parse('SW',OPTS,{'PD':{}})
    sources,_=generate({'SW':item},{'SW':BIND},'Top')
    text=sources[0]+f'''module fixture(input clk);
reg [3:0] phase=0; always @(posedge clk) if(phase<7) phase<=phase+1;
wire reset=phase==0, input_good=1, control=phase<2;
wire output_good={"1" if bad else "phase<3"};
rvw_upf_switch_SW dut(.*); endmodule
'''
    (tmp_path/'design.sv').write_text(text)
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


def test_importer_uses_switch_bindings(tmp_path):
    import json
    from rvw.formal.upf_subset import generate as generate_upf
    source=tmp_path/'power.upf'
    source.write_text('upf_version 2.1\ncreate_power_domain PD -elements {core}\n'+
        'create_power_switch SW -domain PD -input_supply_port {VIN VDD} -output_supply_port {VOUT VDD_SW} -control_port {CTL gate} -on_state {ON VIN CTL}\n')
    b=tmp_path/'bindings.json'
    b.write_text(json.dumps(dict(schema='rvw.upf-bindings/1',top='Top',event_model='always_on_sampled',domains={'PD':{}},switches={'SW':BIND})))
    report=generate_upf(source,b,tmp_path/'out')
    assert report['status']=='generated'
    assert report['unmonitored_domains']==[]
    assert '.control(gate)' in (tmp_path/'out/binds.sv').read_text()
