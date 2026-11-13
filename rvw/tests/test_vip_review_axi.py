"""Regressions from the protocol correctness review."""
import pytest
from rvw.vip.axi import Address, check_address
from rvw.vip.apb import ProtocolError

pytestmark = pytest.mark.fast


def test_exclusive_cannot_exceed_128_bytes():
    with pytest.raises(ProtocolError, match='AXI_EXCLUSIVE'):
        check_address(Address(length=15, size=4, lock=1), data_bytes=16)


def test_128_byte_exclusive_is_valid():
    check_address(Address(length=7, size=4, lock=1), data_bytes=16)
