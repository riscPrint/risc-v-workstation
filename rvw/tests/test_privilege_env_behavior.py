import pytest
from rvw.privilege.env_behavior import programs

pytestmark=pytest.mark.fast


def test_zero_memory_and_trap_matrices():
    rows=programs(dict(isa='rv64imah_zicsr_zicboz',envcfg={'block_bytes':64}))
    assert len(rows)==40 and len({r['id'] for r in rows})==40
    assert all(r['reference_options']==['--blocksz=64'] for r in rows)
    allowed=next(r['assembly'] for r in rows if r['id']=='envcfg-zero-vu-111')
    assert 'zero_check:' in allowed and 'block_before' in allowed and 'block_after' in allowed
    denied=next(r['assembly'] for r in rows if r['id']=='envcfg-zero-vu-110')
    assert 'li t1, 22' in denied and 'denied_check:' in denied
    assert len(programs(dict(isa='rv64im_zicboz',envcfg={'block_bytes':32})))==12


@pytest.mark.parametrize('size',[0,8,48,8192])
def test_invalid_size(size):
    with pytest.raises(ValueError):programs(dict(isa='rv64im_zicboz',envcfg={'block_bytes':size}))
