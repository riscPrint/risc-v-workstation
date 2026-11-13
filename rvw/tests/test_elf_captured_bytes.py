"""C1 loaders must not reopen the source ELF to obtain symbols."""
import struct
import pytest
from rvw.cosim.elf import Elf
pytestmark = pytest.mark.fast

def image():
    data=bytearray(260)
    data[:6]=b'\x7fELF\x02\x01'
    struct.pack_into('<HHIQQQIHHHHHH',data,16,2,243,1,0x100,64,0,0,64,56,1,64,0,0)
    struct.pack_into('<IIQQQQQQ',data,64,1,5,256,0x100,0x100,4,8,4096)
    data[256]=42
    return data

def test_supplied_bytes_do_not_open_source(tmp_path):
    path=tmp_path/'missing.elf'
    parsed=Elf(path,data=image())
    assert parsed.entry==0x100
    assert parsed.segments==[(0x100,b'\x2a\0\0\0',8)]
    assert parsed.symbols=={}
    assert not path.exists()

def test_captured_mutable_buffer_is_frozen(tmp_path):
    data=image();parsed=Elf(tmp_path/'missing.elf',data=data)
    data[256]=0
    assert parsed.data[256]==42

def test_symbols_come_from_the_captured_bytes(tmp_path):
    data=image()+bytearray(380)
    struct.pack_into('<Q',data,40,320)
    struct.pack_into('<H',data,60,3)
    struct.pack_into('<IIQQQQIIQQ',data,384,0,3,0,0,512,8,0,0,1,0)
    struct.pack_into('<IIQQQQIIQQ',data,448,0,2,0,0,536,24,1,0,8,24)
    data[512:520]=b'\0tohost\0'
    struct.pack_into('<IBBHQQ',data,536,1,0,0,1,0x200,8)
    parsed=Elf(tmp_path/'unavailable.elf',data=data)
    assert parsed.symbols['tohost']==0x200
