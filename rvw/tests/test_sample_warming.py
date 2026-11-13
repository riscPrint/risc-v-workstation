import json
import pytest
from rvw.sample import warming

pytestmark=pytest.mark.fast


def test_fixed_roi_warmup_bias(tmp_path,monkeypatch):
    monkeypatch.setattr(warming,'load',lambda _:dict(instructions=20))
    def point(spec,work,point,w):
        work.mkdir(parents=True,exist_ok=True)
        start=point['start_instruction']-w
        (work/'expected.json').write_text(json.dumps([dict(pc=i) for i in range(start,start+w+point['instructions'])]))
        return dict(cpi=3-w/4,ipc=1/(3-w/4))
    monkeypatch.setattr(warming.flow,'run_point',point)
    monkeypatch.setattr(warming.flow,'compare',lambda *a:dict(cpi=2,ipc=.5))
    r=warming.sweep('unused',tmp_path/'out',start=10,length=4,lengths=[0,2,4])
    assert [p['capture'] for p in r['rows']]==[10,8,6]
    assert [p['absolute_bias_percent'] for p in r['rows']]==[50,25,0]
    assert r['smallest_observed_within_target']==4
    assert 'injection unavailable' in r['warming']


def test_invalid_warmup_refused(tmp_path):
    with pytest.raises(ValueError,match='warmup lengths'):
        warming.sweep('unused',tmp_path,start=10,length=4,lengths=[11])
