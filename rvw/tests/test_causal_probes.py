import json
import pytest
from rvw.probes import api
from rvw.probes.check import check
from rvw.perf.kanata import read

pytestmark = pytest.mark.fast


def stream(tmp_path, producer=5):
    probes=[dict(id=i,kind=k,name=k,fields=[[n,64] for n in fields],meta=meta)
            for i,(k,fields,meta) in enumerate([
                ('stage',['id'],dict(stage='X')), ('retire',['id'],{}),
                ('dependency',['id','producer'],{}), ('stall',[],dict(scope='commit',cause='redirect_recovery'))])]
    rows=[[1,0,5],[1,1,5],[2,0,6],[2,2,6,producer],[2,3],[3,1,6]]
    p=tmp_path/'events';p.write_text('\n'.join(json.dumps(x) for x in [dict(schema='rvw.probe-events/1',identity={},probes=probes),*rows,dict(end=True,cycles=4,events={})]))
    return p


def test_dependency_survives_producer_retirement(tmp_path):
    p=stream(tmp_path);out=tmp_path/'k'
    result=api.run_convert(p,'kanata',out)
    assert result['dependencies']==1
    trace=read(out)
    assert trace.dependencies==1 and trace.stalls
    assert check(events=p,consumer='perf-causal')['status']=='present'


def test_unknown_dependency_is_not_invented(tmp_path):
    with pytest.raises(ValueError,match='unknown consumer or producer'):
        api.run_convert(stream(tmp_path,999),'kanata',tmp_path/'k')


def test_consumer_names_missing_dependency_fields(tmp_path):
    p=stream(tmp_path)
    rows=p.read_text().splitlines();h=json.loads(rows[0]);h['probes'][2]['fields']=[['id',64]]
    p.write_text('\n'.join([json.dumps(h),*rows[1:]]))
    # Declaration check reads the full stream, so update the event payload too.
    rows=p.read_text().splitlines();rows[4]=json.dumps([2,2,6]);p.write_text('\n'.join(rows))
    result=check(events=p,consumer='perf-causal')
    assert result['status']=='inconclusive' and 'dependency(id, producer)' in result['missing_probes']
