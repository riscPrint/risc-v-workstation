"""Exact signed arithmetic in the debug reference hart."""
import pytest

from rvw.debug.hart import Hart, Memory

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('a,b', [((1 << 63) - 1, 3), (-(1 << 63) + 1, 3),
                                ((1 << 63) - 1, -3), (-(1 << 63) + 1, -3)])
@pytest.mark.parametrize('funct3', [4, 6])
def test_signed_division_uses_exact_integer_arithmetic(a, b, funct3):
    hart = Hart(Memory([]))
    hart.setx(1, a)
    hart.setx(2, b)
    # div/rem x3, x1, x2
    hart.execute((1 << 25) | (2 << 20) | (1 << 15) | (funct3 << 12) | (3 << 7) | 0x33, 4)
    quotient = abs(a) // abs(b)
    if (a < 0) != (b < 0):
        quotient = -quotient
    expected = quotient if funct3 == 4 else a - b * quotient
    assert hart.x[3] == expected & hart.mask
