import pytest
from rvw.common.bus_trace import word_bus_address

pytestmark=pytest.mark.fast


@pytest.mark.parametrize('address,rmask,wmask,data',[(0x10a1,0,2,0xffffcd00),(0x10a3,15,0,0xdeadbedd)])
def test_word_lane_effective_addresses(address,rmask,wmask,data):
    raw=dict(mem_addr=address,mem_rmask=rmask,mem_wmask=wmask,mem_rdata=data,mem_wdata=data,trap=False)
    mapped=word_bus_address(raw,32)
    assert mapped==dict(raw,mem_addr=0x10a0)
    assert raw['mem_addr']==address


def test_fault_address_is_not_silently_aligned():
    with pytest.raises(ValueError,match='fault'):
        word_bus_address(dict(mem_addr=0x1001,mem_rmask=15,mem_wmask=0,trap=True),32)


def test_idle_address_and_bad_mask():
    raw=dict(mem_addr=0x1001,mem_rmask=0,mem_wmask=0)
    assert word_bus_address(raw,32)==raw
    with pytest.raises(ValueError,match='mask'):
        word_bus_address(dict(raw,mem_rmask=256),32)
