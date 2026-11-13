"""PMA observations use the same default width as the emitted access."""
import pytest
from rvw.regress.mmu_observe import check_pma

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('mode,width', [('sv32', 4), ('sv39', 8)])
def test_default_width_matches_paging_geometry(mode, width):
    scenario = dict(mode=mode, level=0, access='load', expect='success')
    region = dict(name='device', start=0x80200000, size=4096, cacheable=False,
                  widths=[width], read=True, write=True)
    events = [dict(kind='bus_a', cycle=1, address=0x80200000, opcode=4,
                   size_log2=width.bit_length()-1),
              dict(kind='device_state', cycle=2, address=0x80200000,
                   scheduled=False, value=42)]
    assert check_pma(scenario, events, [region])['status'] == 'consistent'
    wrong = [dict(events[0], size_log2=(1 if width == 4 else 2)), events[1]]
    assert check_pma(scenario, wrong, [region])['status'] == 'mismatch'
