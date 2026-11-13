"""Store readback follows the translated address within a superpage."""
import pytest
from rvw.regress.mmu import assembly, DATA
from rvw.regress.mmu_paging import MODES

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('offset', [0, 8])
def test_superpage_readback_replaces_low_ppn_bits(mode, offset):
    g = MODES[mode]
    level = g.levels - 1
    span = 1 << (12 + g.vpn_bits * level)
    row = dict(id='superpage-store', mode=mode, level=level, flags='VRWAD',
               va=(0x40000000 & -span) | (DATA & (span-1)), pa=DATA & -span,
               offset=offset, access='store', expect='success', bins=['store'])
    code = assembly(row).split('check_data:\n', 1)[1].split('check_ad:', 1)[0]
    assert code.startswith(f' li t0, {DATA + offset}\n')
