"""RV64 mcontrol combines sizehi[22:21] with sizelo[17:16]."""
from types import SimpleNamespace
import pytest
from rvw.debug import checks, profile
from rvw.debug.hart import Hart, Memory, DebugEntry

pytestmark = pytest.mark.fast


def test_model_keeps_high_size_bits_and_matches_only_doubleword_store():
    p = profile.normalize({'triggers': {'count': 1, 'types': [2], 'sizes': [0, 1, 5]}})
    hart = Hart(Memory([]), trigger_profile=p['triggers'])
    unit = hart.triggers
    raw = (2 << 60) | (1 << 59) | (1 << 21) | (1 << 16) | (1 << 12) | (1 << 6) | 2
    unit.write(0x7a2, 0x1000, debug=True)
    unit.write(0x7a1, raw, debug=True)
    assert unit.read(0x7a1) & ((3 << 21) | (3 << 16)) == (1 << 21) | (1 << 16)
    unit.check_access(0x1000, 1, store=True, before=True)
    with pytest.raises(DebugEntry):
        unit.check_access(0x1000, 8, store=True, before=True)


def test_compliance_encoder_places_high_size_bits_above_hit():
    value = checks.mc(SimpleNamespace(xlen=64), 2, store=1, size=5)
    assert (value >> 21) & 3 == 1
    assert (value >> 16) & 3 == 1
