"""Store readback compares the architectural signed load result."""
import pytest
from rvw.regress.mmu import assembly

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('width,value,expected', [(1, 255, -1), (1, 256, 0),
                                                (2, 65535, -1), (4, 65535, 65535)])
@pytest.mark.parametrize('mode', ['sv32', 'sv39'])
def test_store_readback_truncates_and_sign_extends(mode, width, value, expected):
    row = dict(id='store-width', mode=mode, level=0, flags='VRWAD', access='store',
               expect='success', bins=['store'], access_width=width, store_value=value)
    code = assembly(row).split('check_data:\n', 1)[1].split('check_ad:', 1)[0]
    assert f' li t1, {expected}\n bne a0, t1, fail\n' in code


@pytest.mark.parametrize('value,stored', [(255, 255), (256, 0)])
def test_pma_device_state_uses_truncated_store_bytes(value, stored):
    from rvw.regress.mmu_observe import check_pma
    scenario = dict(mode='sv39', level=0, access='store', expect='success',
                    access_width=1, store_value=value)
    region = dict(name='device', start=0x80200000, size=4096, cacheable=False,
                  widths=[1], read=True, write=True)
    events = [dict(kind='bus_a', cycle=i, address=0x80200000, opcode=opcode, size_log2=0)
              for i, opcode in [(1, 0), (2, 4)]]
    events.append(dict(kind='device_state', cycle=3, address=0x80200000,
                       scheduled=False, value=stored))
    assert check_pma(scenario, events, [region])['status'] == 'consistent'
