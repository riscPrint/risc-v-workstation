import json
from pathlib import Path
import pytest
from rvw.cosim.checker import check
from rvw.cosim.platform import Platform
from test_state import fixture, Model

pytestmark = pytest.mark.fast

@pytest.mark.parametrize('required,status',[(False,'match'),(True,'inconclusive')])
def test_integer_trace_has_explicit_fp_scope(tmp_path,required,status):
    header,row=fixture();header['schema']='rvw.rvfi/1'
    for key in ('fd_valid','fd','fd_wdata','fflags','fcsr'):row.pop(key,None)
    trace=tmp_path/'trace.jsonl'
    trace.write_text('\n'.join(map(json.dumps,[header,row,dict(event='end',cycle=2,status='pass')])))
    source=Path(__import__('rvw.cosim.platform',fromlist=['x']).__file__).parent/'configs/boom.json'
    data=json.loads(source.read_text())
    if required: data['require_fp_state']=True
    path=tmp_path/'platform.json';path.write_text(json.dumps(data))
    platform=Platform.load(None,path)
    result=check(trace,Model(row),platform,sync=())
    assert result['status']==status
    assert result['state_coverage']['fp'] is False
    assert result['scope']=='no_fp_state'
    if required:assert result['cause']=='fp_state_not_observed'


def test_fp_requirement_must_be_boolean(tmp_path):
    source=Path(__import__('rvw.cosim.platform',fromlist=['x']).__file__).parent/'configs/boom.json'
    data=json.loads(source.read_text());data['require_fp_state']='yes'
    path=tmp_path/'platform.json';path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='require_fp_state must be a boolean'):
        Platform.load(None,path)


@pytest.mark.parametrize('isa,scoped', [('rv64g',True),('rv64imafdc',True),
    ('rv64i2p1m2p0f2p2',True),('rv64i2p1_m2p0_f2p2_d2p2',True),('rv64i_zfinx',False)])
def test_fp_scope_uses_scalar_fp_extensions(isa,scoped):
    from types import SimpleNamespace
    from rvw.cosim.fp_scope import apply_scope
    extra={}
    assert apply_scope('match',extra,SimpleNamespace(isa=isa,require_fp_state=False),False)=='match'
    assert (extra.get('scope')=='no_fp_state')==scoped
