"""Reference reduction never promotes missing evidence to a mismatch."""
from types import SimpleNamespace
import pytest
from rvw.reduce import reference

pytestmark = pytest.mark.fast


def setup(monkeypatch, comparison):
    run=SimpleNamespace(inconclusive=None, result=SimpleNamespace(instret=2),
        get=lambda key: {'status':'pass','core':'fixture'}[key], artifact=lambda _: 'trace')
    def compare(*a, **kw):
        assert kw['strict'] is True and kw['model']=='spike' and kw['core']=='fixture'
        return comparison
    monkeypatch.setattr(reference,'cosim',compare)
    return run


def test_mismatch_fields_define_reduction_signature(monkeypatch):
    run=setup(monkeypatch,dict(status='mismatch',mismatch={'differences':{'csr[0x340]':{},'rd_wdata':{}}}))
    result=reference.check(run,'elf','platform')
    assert result['status']=='mismatch'
    assert result['signature']=='cosim:csr[0x340],rd_wdata'


@pytest.mark.parametrize('changes,expected',[({},'different'),({'instructions':1},'inconclusive'),
    ({'applied_masks':['csr']},'inconclusive'),({'synchronized':1},'inconclusive'),
    ({'status':'error'},'inconclusive'),({'status':'mismatch'},'inconclusive'),
    ({'trace_complete':False},'inconclusive')])
def test_complete_unmasked_match_is_only_reference_nonmatch(monkeypatch,changes,expected):
    comparison=dict(status='match',trace_complete=True,end_status='pass',instructions=2)
    comparison.update(changes)
    assert reference.check(setup(monkeypatch,comparison),'elf','platform')['status']==expected


def test_inconclusive_c1_never_launches_reference(monkeypatch):
    run=setup(monkeypatch,{})
    run.inconclusive='changed source'
    monkeypatch.setattr(reference,'cosim',lambda *a,**kw:pytest.fail('no reference for inconclusive C1'))
    assert reference.check(run,'elf','platform')['status']=='inconclusive'


def test_passing_c1_can_reduce_a_reference_mismatch(tmp_path, monkeypatch):
    from test_debug_tools import fake_run, CFG
    from rvw.reduce.core import Reducer, Options
    config=tmp_path/'debug.toml'; config.write_text(CFG)
    monkeypatch.setenv('RVW_CORE_CONFIG',str(config))
    monkeypatch.setenv('RVW_NO_LOCK','1')
    run=fake_run(tmp_path/'run','--seed','1','--rvfi-trace')
    platform=tmp_path/'platform.json'; platform.write_text('{}')
    monkeypatch.setattr(reference,'cosim',lambda *a,**kw:dict(status='mismatch',
        mismatch={'differences':{'csr[0x340]':{'expected':'0','actual':'1'}}}))
    result=Reducer(str(run),Options(cosim_platform=str(platform),out=tmp_path/'reduced',
                                   modes=['cycles'],budget=1)).reduce()
    assert result['reproduced']
    assert result['signature']=='cosim:csr[0x340]'
    assert result['trials'][0]['status']=='pass'
    assert result['trials'][0]['reference']['status']=='mismatch'
    assert result['original_reference']['status']=='mismatch'


def test_missing_reference_evidence_refuses_passing_original(tmp_path,monkeypatch):
    from test_debug_tools import fake_run
    from rvw.reduce.core import Reducer, Options
    run=fake_run(tmp_path/'run','--seed','1','--rvfi-trace')
    platform=tmp_path/'platform.json';platform.write_text('{}')
    monkeypatch.setattr(reference,'cosim',lambda *a,**kw:dict(status='error'))
    with pytest.raises(ValueError,match='no conclusive strict Spike mismatch'):
        Reducer(str(run),Options(cosim_platform=str(platform),out=tmp_path/'reduced'))
