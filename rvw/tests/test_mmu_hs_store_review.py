"""The HS entry must run the same operand setup as the M entry."""
import pytest
from rvw.regress import mmu
from rvw.regress.mmu_hypervisor import matrix

pytestmark = pytest.mark.fast


def test_hs_store_initializes_operand_after_mret():
    scenario = next(s for s in matrix() if s['guest_op'] == 'hsv.d' and s['expect'] == 'success')
    scenario = dict(scenario, guest_trap='hs')
    code = mmu.assembly(scenario)
    target = code.split('csrw mepc, t0', 1)[0].split('la t0, ')[-1].strip()
    entry = code.split(target + ':\n', 1)[1].split('hsv.d a0, (t3)', 1)[0]
    assert 'li a0, 43' in entry
