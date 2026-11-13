import json
import pytest
from rvw.sec.ift import shadow, path
from rvw.sec.common import publish

pytestmark = pytest.mark.fast


def netlist():
    return {'modules':{'unit':{'ports':{
        'clk':{'direction':'input','bits':[2]},'reset':{'direction':'input','bits':[3]},
        'secret':{'direction':'input','bits':[4]},'bus':{'direction':'output','bits':[5]}},
        'netnames':{n:{'bits':[b]} for n,b in [('clk',2),('reset',3),('secret',4),('bus',5)]},
        'cells':{'gate':{'type':'$_AND_','connections':{'A':[4],'B':['0'],'Y':[6]}},
                 'reg':{'type':'$_DFF_P_','connections':{'D':[6],'C':[2],'Q':[5]}}}}}}


def test_modes_and_paths():
    d = netlist(); d['modules']['unit']['netnames']['temp']={'bits':[6]}
    p = dict(clock='clk',reset='reset',sources=['secret'],sinks=['bus'])
    a,_ = shadow(d,'unit',p)
    b,_ = shadow(d,'unit',p,'conservative')
    assert a != b
    assert 'assign t6 = t4;' in b
    assert path(d,'unit',['secret'],'bus') == ['secret','gate','reg','bus']
    with pytest.raises(ValueError):
        shadow(d,'unit',{**p,'sources':['clk']})


def test_result_is_not_security_proof(tmp_path):
    r=publish(tmp_path,'ift',[],False)
    assert r['status']=='inconclusive'
    assert json.loads((tmp_path/'results.json').read_text())['tests'][0]['status']=='error'


def test_contract_eligibility():
    from rvw.sec.pairs import compare, generate
    plan=dict(contract='constant-time',observations=['cache'],clauses=['pc','memory'])
    row=dict(pc=16,insn=0x33,mem_addr=0,mem_rmask=0,mem_wmask=0)
    a=dict(reference=[row],public={},secret=0,observations={'cache':[1]})
    b={**a,'secret':1,'observations':{'cache':[2]}}
    assert compare(a,b,plan)['status']=='violation'
    assert compare(a,{**b,'reference':[{**row,'pc':20}]},plan)['status']=='ineligible'
    assert generate(12,4)==generate(12,4)
    with pytest.raises(ValueError): compare(a,a,plan)


def test_c6_dependency_path(gcd_db):
    from rvw.sec.ift import database_path
    result=database_path(gcd_db,'io_a','io_result')
    assert result['found']
    assert result['input_capture']
    missing=database_path(gcd_db,'unknown_security_source','io_result')
    assert missing['inconclusive'] and not missing['found']
