"""Project-owned loader checks; no RTL pass is claimed by these tests."""
import importlib.util
from pathlib import Path
import struct
import pytest

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('ibex_adapter', ROOT/'examples/ibex/rvw/adapter.py')
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)

def elf(address=0x80000080, entry=0x80000080):
    data=bytearray(88)
    data[:6]=b'\x7fELF\x01\x01'
    struct.pack_into('<II',data,24,entry,52)
    struct.pack_into('<HH',data,42,32,1)
    struct.pack_into('<8I',data,52,1,84,address,address,4,8,5,4)
    data[84:]=b'ABCD'
    return bytes(data)

def test_ibex_load_segment_and_zero_bss():
    ram=adapter.image(elf())
    assert ram[128:136]==b'ABCD\0\0\0\0'

@pytest.mark.parametrize('data',[elf(address=0x7fffffff),elf(address=0x800ffffc),elf(entry=0x80000000),b'bad elf'])
def test_ibex_refuse_wrong_image(data):
    with pytest.raises(ValueError): adapter.image(data)
