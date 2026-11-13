import json
import pytest
from rvw.regress.act4 import selection
from test_act4 import profile
pytestmark = pytest.mark.fast

@pytest.mark.parametrize('offset,valid',[(0x80,True),(-4,False),(0x1000000,False)])
def test_reset_inside_ram(tmp_path,offset,valid):
    p,_=profile(tmp_path)
    f=tmp_path/'platform.json';d=json.loads(f.read_text());d['reset_pc']=hex(0x80000000+offset);f.write_text(json.dumps(d))
    if valid: assert selection(p)['isa']=='rv32im_zicsr_zifencei'
    else:
        with pytest.raises(ValueError,match='containing reset_pc'):selection(p)


def test_udb_cache_name_tracks_architecture():
    from rvw.regress.act4 import architecture_config
    data={'extensions':{'i':'= 2.1','sm':'= 1.12.0'},'params':{'MXLEN':32}}
    first=architecture_config(data)
    assert first['name']==architecture_config(data)['name']
    assert first['name'].startswith('rvw-act4-')
    data['params']['MXLEN']=64
    assert architecture_config(data)['name']!=first['name']
    data['params']['MXLEN']=32
    data['extensions']['m']='= 2.0'
    assert architecture_config(data)['name']!=first['name']
