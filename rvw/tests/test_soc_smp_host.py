"""Host-owned RAM retains software metadata without a duplicate RTL memory."""
import json
from pathlib import Path
import pytest
from rvw.soc.compose import compose

pytestmark=pytest.mark.fast
ROOT=Path(__file__).resolve().parents[2]


def configuration(tmp_path):
    model=json.loads((ROOT/'SpinalSoc/examples/vex/soc.json').read_text())
    model['platform'].update(xlen=64,isa='rv64ima_zicsr_zifencei',reference_isa='rv64ima_zicsr_zifencei')
    model['regions']=[r for r in model['regions'] if r['name']=='ram']
    model['regions'][0]['size']=0x2000000
    model['interrupts']=[]
    (tmp_path/'map.json').write_text(json.dumps(model))
    spec=dict(schema='rvw.soc-compose/1',map='map.json',clock_hz=100000000,reset='async_high',
              core={'class':'project.Host','bus':'simple'},devices=dict(ram=dict(type='host')))
    path=tmp_path/'compose.json';path.write_text(json.dumps(spec))
    return path,spec


def test_host_ram_has_no_duplicate_rtl(tmp_path):
    path,_=configuration(tmp_path)
    result=compose(path,tmp_path/'out')
    manifest=json.loads((tmp_path/'out/composition.json').read_text())
    assert result['profile']=='simple-rv64-byte'
    assert manifest['memories']==[dict(name='ram',host=True,base=0x80000000,size=0x2000000)]
    assert manifest['bus_ports']==['core.bus']
    assert 'WordMemory(' not in (tmp_path/'out/ComposedSoc.scala').read_text()
    assert json.loads((tmp_path/'out/platform.json').read_text())['xlen']==64


def test_host_binder_cannot_hide_domains(tmp_path):
    path,spec=configuration(tmp_path)
    spec['devices']['ram']['domain']='slow';path.write_text(json.dumps(spec))
    with pytest.raises(ValueError,match='expected fields'):compose(path,tmp_path/'out')
