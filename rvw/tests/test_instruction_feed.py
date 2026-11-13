"""Instruction source words preserve ELF bytes and never overwrite a prior feed."""
import json,struct
from hashlib import sha256
import pytest
from rvw.regress.instruction_feed import generate
pytestmark=pytest.mark.fast


def image(tmp_path):
    header=bytearray(84)
    header[:7]=b'\x7fELF\x01\x01\x01'
    struct.pack_into('<HHIIIIIHHHHHH',header,16,2,243,1,0x80000000,52,0,0,52,32,1,40,0,0)
    struct.pack_into('<IIIIIIII',header,52,1,84,0x80000000,0x80000000,8,16,5,4)
    p=tmp_path/'program';p.write_bytes(header+struct.pack('<II',0x00500293,0x13));return p


def test_feed_preserves_little_endian_words_and_reference_hash(tmp_path):
    elf=image(tmp_path);out=tmp_path/'feed.json'
    result=generate(elf,out)
    data=json.loads(out.read_text())
    assert result['reference_elf_sha256']==sha256(elf.read_bytes()).hexdigest()
    assert data['words']==[{'address':'0x80000000','data':'0x500293'},{'address':'0x80000004','data':'0x13'}]
    with pytest.raises(FileExistsError):generate(elf,out)


def test_wide_bus_packs_two_32_bit_instructions(tmp_path):
    elf=image(tmp_path);out=tmp_path/'feed.json';generate(elf,out,8)
    assert json.loads(out.read_text())['words']==[{'address':'0x80000000','data':hex(0x13<<32|0x00500293)}]
