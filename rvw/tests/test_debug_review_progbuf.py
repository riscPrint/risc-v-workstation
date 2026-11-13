"""Program buffer instruction fetch supports both instruction lengths."""
import pytest
from rvw.debug.hart import Hart, Memory

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('image,expected', [
    (bytes.fromhex('01000290'), 0),  # c.nop; c.ebreak
    (bytes.fromhex('0544050402900000'), 2),  # c.li s0,1; c.addi s0,1; c.ebreak
    (bytes.fromhex('0100130470000290'), 7),  # c.nop; addi s0,zero,7; c.ebreak
])
def test_program_buffer_fetches_halfwords(image, expected):
    hart = Hart(Memory([]))
    hart.debug_mode = True
    words = [int.from_bytes(image[i:i+4], 'little') for i in range(0, len(image), 4)]
    assert hart.run_debug(words, 0x800) is None
    assert hart.x[8] == expected
