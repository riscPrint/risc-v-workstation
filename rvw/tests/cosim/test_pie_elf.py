"""ELF fixtures check loader placement, not Linux execution."""
import struct
import pytest
from rvw.cosim.elf import Elf


def image(tmp_path, kind=3, segment_type=1):
    d = bytearray(260)
    d[:6] = b'\x7fELF\x02\x01'
    struct.pack_into('<HHIQQQIHHHHHH', d, 16, kind, 243, 1, 0x100, 64, 0, 0, 64, 56, 1, 64, 0, 0)
    struct.pack_into('<IIQQQQQQ', d, 64, segment_type, 5, 256, 0x100, 0x100, 4, 8, 4096)
    d[256] = 42
    p = tmp_path / 'firmware.elf'
    p.write_bytes(d)
    return p


def test_pie_default_link_address(tmp_path):
    e = Elf(image(tmp_path))
    assert e.entry == 0x100
    assert e.segments == [(0x100, b'\x2a\0\0\0', 8)]


def test_pie_explicit_bias(tmp_path):
    e = Elf(image(tmp_path), load_bias=0x80000000)
    assert e.entry == 0x80000100
    assert e.segments[0][0] == 0x80000100


@pytest.mark.parametrize('kind,segment_type,bias', [(1, 1, 0), (3, 3, 0), (2, 1, 4096), (3, 1, -1)])
def test_unsupported_loader_contract(tmp_path, kind, segment_type, bias):
    with pytest.raises(ValueError):
        Elf(image(tmp_path, kind, segment_type), load_bias=bias)
