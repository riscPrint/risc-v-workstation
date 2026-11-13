import pytest
from rvw.cov.actions import lower
from rvw.cov.sequence import KINDS


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('distance', [1,2,4])
def test_bounded_actions(kind, distance):
    result = lower(f'sequence:["{kind}",{distance}]', [5,6,7], memory=True)
    assert result['status'] == 'generated'
    assert len(result['actions']) == distance+1
    assert result['measured_hits'] == []
    assert result['actions'][-1]['after'] == distance-1
    assert result['source_text'].count('rvw_payload_start:') == 1
    if 'load' in kind or 'store' in kind:
        assert 'la x7, rvw_action_scratch' in result['source_text']
    assert result == lower(f'sequence:["{kind}",{distance}]', [5,6,7], memory=True)


def test_missing_memory_and_unsupported_bound():
    assert lower('sequence:["load-after-store",1]', [5,6,7])['status'] == 'unsupported'
    assert lower('sequence:["RAW",3]', [5,6,7])['status'] == 'unsupported'
    with pytest.raises(ValueError):
        lower('sequence:["RAW",1]',[0,1,2])


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('distance', [1,2,4])
def test_encoded_actions_independently_reach_retirement_pair(kind,distance):
    from rvw.common.riscv import decode
    from rvw.cov.sequence import observe
    result = lower(f'sequence:["{kind}",{distance}]',[5,6,7],memory=True)
    history, seen = [], []
    for index,word in enumerate(result['instructions']):
        info = decode(word,32).as_dict()
        assert info['class'] != 'unknown'
        rd = word>>7 & 31
        dest = ('x',rd) if info['dest_bank']=='x' and rd else None
        seen += observe(history,{'order':index},info,dest,[distance])
    assert any(row['kind']==kind and row['distance']==distance for row in seen)


def test_api_replays_same_source(tmp_path):
    from rvw.cov.action_cli import execute_json
    a=execute_json(goal='sequence:["RAW",2]',work_dir=tmp_path/'a',registers=[5,6,7])
    b=execute_json(goal='sequence:["RAW",2]',work_dir=tmp_path/'b',registers='5,6,7')
    assert a['source_sha256']==b['source_sha256']
    assert a['instructions']==b['instructions'] and a['measured_hits']==[]
