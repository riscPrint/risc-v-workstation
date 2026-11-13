"""Lasso snapshots must use declared Verilog bit indices."""
import pytest
from rvw.formal.liveness_app import state_bits

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('offset,upto,expected', [
    (4, 0, ['\\q [4]', '\\q [5]']),
    (4, 1, ['\\q [5]', '\\q [4]']),
])
def test_state_snapshot_respects_packed_range(offset, upto, expected):
    module = dict(netnames={'q': dict(bits=[2, 3], offset=offset, upto=upto)},
                  cells={'ff': dict(type='$dff', parameters={'CLK_POLARITY': '1'},
                                    connections={'Q': [2, 3]})})
    assert state_bits(module) == expected
