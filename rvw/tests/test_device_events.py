import copy
import json
from pathlib import Path
import pytest
from rvw.soc.device_events import check

ROOT = Path(__file__).resolve().parents[2]


pytestmark = pytest.mark.fast


def inputs(tmp_path):
    model = json.loads((ROOT/'examples/boom/soc.json').read_text())
    region = next(r for r in model['regions'] if r['registers'])
    reg = region['registers'][0]
    reg.update(reset=7,access='rw',read_action='clear',write_action='normal')
    address = int(region['base'],0)+int(reg['offset'],0) if isinstance(reg['offset'],str) else int(region['base'],0)+reg['offset']
    p = tmp_path/'model.json'; p.write_text(json.dumps(model))
    def request(master,tag,write=False,data=0):
        return dict(kind='request',cycle=1,master=master,id=tag,address=address,size=reg['width']//8,write=write,data=data)
    events = [request('cpu',0),request('dma',0,True,12),
              dict(kind='hardware',cycle=1,address=address,increment=2,set=1),
              dict(kind='response',cycle=2,master='dma',id=0,error=False),
              dict(kind='response',cycle=2,master='cpu',id=0,error=False,data=7),
              dict(kind='state',cycle=3,address=address,value=15)]
    return p,events


def run(tmp_path,model,events):
    p=tmp_path/'trace.json'; p.write_text(json.dumps(dict(schema='rvw.device-events/1',linearization='accepted_request',events=events)))
    return check(model,p)


def test_independent_concurrent_masters_and_events(tmp_path):
    model,events=inputs(tmp_path)
    result=run(tmp_path,model,events)
    assert result['status']=='inconclusive'
    assert all(c['match'] for c in result['checks'])
    assert result['masters']==['cpu','dma']
    assert result['outstanding']==[]


@pytest.mark.parametrize('fault',['data','state','duplicate','unsolicited','response_error'])
def test_faults(tmp_path,fault):
    model,events=inputs(tmp_path)
    if fault=='data': events[4]['data']=0
    if fault=='state': events[5]['value']=0
    if fault=='duplicate': events.insert(1,copy.deepcopy(events[0]))
    if fault=='unsolicited': events[4]['id']=9
    if fault=='response_error': events[3]['error']=True
    assert run(tmp_path,model,events)['status']=='mismatch'


def test_missing_responses_remain_inconclusive(tmp_path):
    model,events=inputs(tmp_path)
    result=run(tmp_path,model,events[:2])
    assert result['status']=='inconclusive'
    assert len(result['outstanding'])==2


def test_negative_or_out_of_order_cycles_refused(tmp_path):
    model,events=inputs(tmp_path)
    events[0]['cycle']=-1
    with pytest.raises(ValueError,match='nonnegative'):
        run(tmp_path,model,events)
    events[0]['cycle']=2
    with pytest.raises(ValueError,match='ordered'):
        run(tmp_path,model,events)
