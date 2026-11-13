import json
import pytest
from rvw.sec.isolation import run
from rvw.sec.pairs import compare
pytestmark=pytest.mark.fast


def test_post_boundary_contract():
    plan=dict(contract='sandboxing',observations=['cycles'],clauses=['pc'],contract_start_pc=32)
    a=dict(reference=[dict(pc=16),dict(pc=32)],public={},secret=0,observations={'cycles':3})
    b=dict(reference=[dict(pc=20),dict(pc=32)],public={},secret=1,observations={'cycles':4})
    assert compare(a,b,plan)['status']=='violation'
    with pytest.raises(ValueError): compare(a,{**b,'reference':[dict(pc=20)]},plan)


def test_isolation_refuses_missing_boundary(tmp_path):
    p=tmp_path/'plan.json';p.write_text(json.dumps(dict(isolation_kind='epmp',program=['nop'])))
    with pytest.raises(ValueError,match='boundary'): run(p,tmp_path/'out')
