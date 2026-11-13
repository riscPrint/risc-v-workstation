from pathlib import Path
import pytest
from rvw.formal import revision_bench

pytestmark=pytest.mark.fast


@pytest.mark.parametrize('warm_status',['pass','inconclusive'])
def test_alternating_fresh_trials_and_no_savings_on_unproved_result(tmp_path,monkeypatch,warm_status):
    calls=[]
    def lemma(plan,root,out,library=None,**kwargs):
        out.mkdir(parents=True)
        if library is None:
            (out/'library.json').write_text('{}')
            return {'status':'pass'}
        calls.append('reuse')
        assert library.is_file()
        return {'status':warm_status,'entries':[{'cone_sha256':'abc'}]}
    def cold(plan,root,out,**kwargs):
        out.mkdir(parents=True);calls.append('cold');return {'status':'pass'}
    monkeypatch.setattr(revision_bench,'lemmas',lemma)
    monkeypatch.setattr(revision_bench,'race',cold)
    r=revision_bench.measure({'sources':[{'sha256':'old'}]}, {'sources':[{'sha256':'new'}]},tmp_path,tmp_path/'out',trials=2)
    assert calls==['cold','reuse','reuse','cold']
    assert len(r['trials'])==4
    if warm_status=='pass':assert 'saved_s' in r
    else:assert r['status']=='inconclusive' and 'saved_s' not in r


def test_invalid_trials_rejected(tmp_path):
    with pytest.raises(ValueError):revision_bench.measure({}, {},tmp_path,tmp_path/'out',trials=0)
