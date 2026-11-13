"""Fetch alignment is separate from the instruction count width."""
import pytest
from rvw.ooo.core import Instruction
from rvw.ooo.frontend import Frontend, FrontendConfig

pytestmark = pytest.mark.fast


def test_single_block_limit_at_offset_target():
    ops = [Instruction("alu", pc=4), Instruction("alu", pc=8)]
    unrestricted = Frontend({"block_bytes": 8}, 2, 8)
    unrestricted.advance(0, ops)
    assert unrestricted.position == 2
    limited = Frontend({"block_bytes": 8, "fetch_blocks_per_cycle": 1}, 2, 8)
    limited.advance(0, ops)
    assert limited.position == 1
    assert limited.events["fetch_block_limit_cycles"] == 1
    limited.advance(1, ops)
    assert limited.position == 2


def test_same_block_keeps_full_width():
    ops = [Instruction("alu", pc=8), Instruction("alu", pc=12)]
    limited = Frontend({"block_bytes": 8, "fetch_blocks_per_cycle": 1}, 2, 8)
    limited.advance(0, ops)
    assert limited.position == 2


def test_negative_limit_is_an_error():
    with pytest.raises(ValueError):
        FrontendConfig(fetch_blocks_per_cycle=-1)
