import json
from pathlib import Path
import pytest
from rvw.formal.upf_subset import generate

pytestmark = pytest.mark.fast


def inputs(tmp_path):
    source=tmp_path/'intent.upf';source.write_text('upf_version 2.1\ncreate_power_domain core -elements {u_core}\n')
    b={'schema':'rvw.upf-bindings/1','top':'top','event_model':'always_on_sampled','domains':{'core':{}},
       'clock_gates':{'core_clock':{'domain':'core','wake_cycles':3,'clk':'aon_clk','reset':'rst',
                       'enable':'gate_en','source_low':'src_low','clock_edge':'edge_seen','work_pending':'pending','wakeup':'wake'}}}
    path=tmp_path/'bindings.json';path.write_text(json.dumps(b));return source,path,b


def test_explicit_gate_reuses_existing_sampled_monitor(tmp_path):
    source,path,b=inputs(tmp_path)
    result=generate(source,path,tmp_path/'out')
    assert result['status']=='generated' and result['clock_gates']==['core_clock']
    assert result['unmonitored_domains']==[]
    monitor=(tmp_path/'out/monitors.sv').read_text()
    assert 'assert(wake_age < 3)' in monitor
    assert 'assert(source_low)' in monitor
    assert '.clk(aon_clk)' in (tmp_path/'out/binds.sv').read_text()
    assert result['intent'].get('clock_gates') is None


@pytest.mark.parametrize('fault',['domain','bound','expression','missing','extra'])
def test_refuse_incomplete_or_dynamic_gate_bindings(tmp_path,fault):
    source,path,b=inputs(tmp_path);gate=b['clock_gates']['core_clock']
    if fault=='domain':gate['domain']='absent'
    if fault=='bound':gate['wake_cycles']=False
    if fault=='expression':gate['enable']='en || test'
    if fault=='missing':gate.pop('source_low')
    if fault=='extra':gate['policy']='guessed'
    path.write_text(json.dumps(b))
    with pytest.raises(ValueError):generate(source,path,tmp_path/'out')
    assert not (tmp_path/'out').exists()
