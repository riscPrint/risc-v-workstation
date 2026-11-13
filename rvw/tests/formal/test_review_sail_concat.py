"""Keep packed operands when lowering Sail temporary slices."""
import pytest
from rvw.formal.sail_m import lower
from rvw.formal.sail_zicond import lower_temporary_slices

pytestmark = pytest.mark.fast


def test_temporary_slice_preserves_concatenation_operands():
    # Truncating a 64-bit pair to 40 bits must keep all of b and low bits of a.
    assert lower('assign y = {a, b}[39:0];', 'mul') == "assign y = 40'({a, b});"


def test_shared_backend_slice_preserves_concatenation_operands():
    assert lower_temporary_slices('assign y = {a, b}[39:0];') == "assign y = 40'({a, b});"
