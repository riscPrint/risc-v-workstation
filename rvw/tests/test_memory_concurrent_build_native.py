import hashlib
import json
from pathlib import Path
import shutil
import struct
import pytest
from rvw.memory.concurrent_build import build, STRIDE
from rvw.runs.elf import Elf


def test_native_per_hart_elfs_match_shared_harness_and_axiomatic_inputs(tmp_path):
    compiler=shutil.which('riscv64-unknown-elf-gcc')
    if not compiler:
        compiler='/opt/homebrew/opt/riscv-gnu-toolchain/bin/riscv64-unknown-elf-gcc'
        if not Path(compiler).is_file():
            pytest.skip('RISC-V GCC is not installed')
    root=tmp_path/'seed7'
    report=build(root, seed=7, harts=3, length=20, gcc=compiler)
    assert report['status']=='built' and not report['executed']
    assert report['ordering']=='not_checked' and report['rtl']=='not_run'
    manifest=json.loads(Path(report['hart_images']).read_text())
    reference=json.loads(Path(report['reference']).read_text())
    assert manifest['schema']=='rvw.hart-images/1' and len(manifest['harts'])==3
    assert len(reference['locations'])==8
    shared=[]
    private=[]
    for row, metadata in zip(manifest['harts'], report['programs']):
        path=Path(row['elf']); elf=Elf(str(path)); symbols=elf.symbols()
        assert hashlib.sha256(path.read_bytes()).hexdigest()==row['elf_sha256']
        assert int(metadata['entry'], 0)==symbols['_start'].value==0x80000000+row['hart']*STRIDE
        assert int(metadata['completion_pc'], 0)==symbols[metadata['completion_symbol']].value
        assert elf.read_int('tohost', 8)==0 and symbols['rvw_shared'].value==0x81000000
        assert {'address': metadata['tohost'], 'size': 8, 'value': '0x0'} in reference['locations']
        segments=[]
        for index in range(elf.phnum):
            values=struct.unpack_from('<IIQQQQQQ', elf.data, elf.phoff+index*elf.phentsize)
            typ, flags, offset, va, pa, filesz, memsz, align=values
            if typ==1:
                segments.append((pa, memsz, bytes(elf.data[offset:offset+filesz])))
        assert len(segments)==2
        shared.append(next(s for s in segments if s[0]==0x81000000))
        private.append(next(s for s in segments if s[0]!=0x81000000))
    assert shared==[(0x81000000, 40, b'')]*3
    for i, a in enumerate(private):
        for b in private[i+1:]:
            assert a[0]+a[1] <= b[0]
