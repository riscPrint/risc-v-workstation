"""Compiler-backed per-hart ELF rewriting controls. No RTL oracle here."""
import hashlib
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
import pytest
from rvw.common.proc import run_group
from rvw.reduce.hart_instructions import reduce_hart_instructions
from rvw.reduce.streams import instruction_slots
from rvw.runs.elf import Elf
from test_reduce_device_rx import Command


def setup(tmp_path):
    gcc=shutil.which('riscv64-unknown-elf-gcc') or '/opt/homebrew/opt/riscv-gnu-toolchain/bin/riscv64-unknown-elf-gcc'
    if not Path(gcc).exists():pytest.skip('RISC-V GCC required')
    source=tmp_path/'stream.S'
    source.write_text('.text\n.global stream\n.type stream,@function\nstream:\n.option norvc\naddi a0,a0,1\naddi a1,a1,2\naddi a2,a2,3\n.size stream,.-stream\n')
    rows=[]
    for hart in range(2):
        elf=tmp_path/f'hart{hart}.elf'
        built=run_group([gcc,'-march=rv32im','-mabi=ilp32','-nostdlib','-Wl,-e,stream',
            '-Ttext='+hex(0x80000000+hart*0x10000),str(source),'-o',str(elf)],capture=True,timeout=30)
        assert built.returncode==0,built.stderr
        rows.append(dict(hart=hart,elf=str(elf),elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest()))
    manifest=tmp_path/'harts.json';manifest.write_text(json.dumps(dict(schema='rvw.hart-images/1',harts=rows)))
    capture=SimpleNamespace(file=lambda p:SimpleNamespace(copy=Path(p),sha256=hashlib.sha256(Path(p).read_bytes()).hexdigest()))
    r=SimpleNamespace(o=SimpleNamespace(hart_symbols=['1:stream']),best=dict(cmd=Command(hart_images=str(manifest),elf=rows[0]['elf']),elf=rows[0]['elf']),
        run={'details':{'hart_images':rows}},out=tmp_path,trials=[],inputs=SimpleNamespace(capture=capture,root=tmp_path))
    return r,rows


def test_patch_one_hart_and_keep_primary_and_inventory(tmp_path):
    r,rows=setup(tmp_path)
    def search(name,items,command):
        assert name=='hart:1:stream' and list(items)==[0,1,2]
        cmd,meta=command([1])
        data=json.loads(Path(cmd['hart_images']).read_text())
        assert [v['hart'] for v in data['harts']]==[0,1]
        assert data['harts'][0]==rows[0] and cmd['elf']==rows[0]['elf']
        image=Elf(data['harts'][1]['elf']);original=Elf(rows[1]['elf'])
        for i,(offset,size) in enumerate(instruction_slots(original,'stream')):
            assert image.data[offset:offset+size]==(original.data[offset:offset+size] if i==1 else bytes.fromhex('13000000'))
        assert len(image.data)==len(original.data)
        assert meta['hart']==1 and meta['instructions_kept']==[1]
    r._stream_search=search
    reduce_hart_instructions(r)


def test_refuse_changed_image(tmp_path):
    r,rows=setup(tmp_path)
    path=Path(rows[1]['elf']);path.write_bytes(path.read_bytes()+b'changed')
    with pytest.raises(ValueError,match='digest'):reduce_hart_instructions(r)
