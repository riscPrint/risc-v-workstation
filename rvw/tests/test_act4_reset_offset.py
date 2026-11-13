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
