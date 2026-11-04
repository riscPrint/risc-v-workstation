"""CPU replay must reject missing or inconsistent C1/C2 evidence."""
import json
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from rvw.sim import uvm_cpu
from rvw.cosim.platform import Platform

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def capture(tmp_path, monkeypatch):
    elf = tmp_path / 'elf'
    elf.write_bytes(b'captured elf')
    monkeypatch.setattr(uvm_cpu,'Elf',lambda _: NS(xlen=32,segments=[(0x80000000,b'\x13\x00\x00\x00',4)]))
    trace = tmp_path / 'rvfi.jsonl'
    header = dict(schema='rvw.rvfi/1', core='vexriscv',config='rv32im',xlen=32,
                  isa='rv32im_zicsr_zifencei',elf='original.elf')
    row = dict(order=0,cycle=1,mode=3,rs1=0,rs2=0,rd=0,mem_rmask=0,mem_wmask=0,
               trap=False,intr=False,halt=False,mem_fault=False,
               pc='0x80000000',pc_next='0x80000004',insn='0x13',rs1_rdata='0x0',
               rs2_rdata='0x0',rd_wdata='0x0',mem_addr='0x0',mem_rdata='0x0',mem_wdata='0x0')
    end = dict(event='end',cycle=2,status='pass')
    args = NS(elf=elf,trace=trace)
    inputs = NS(args=args,core_run=dict(schema='rvw.run/1',status='pass',core='vexriscv',
                config='rv32im',instret=1,elf_sha256=uvm_cpu.uvm.sha(elf)),
                platform=Platform.load(None,ROOT/'examples/vexriscv/rvw/platform.json'),
                shim={'library':{'copy':'/tmp/shim'},'source':{'sha256':'source'},
                      'manifest_data':{'build_id':'build'}})
    def write():
        trace.write_text('\n'.join(json.dumps(r) for r in (header,row,end))+'\n')
    write()
    return inputs,header,row,end,write


def test_dpi_inputs_are_from_capture(capture,tmp_path):
    inputs,_,_,_,_ = capture
    rows = uvm_cpu.prepare(inputs,tmp_path)
    assert len(rows)==1
    assert (tmp_path/'records.txt').read_text().startswith('1\n80000000 80000004 13 ')
    assert 'uint64_t fd_wdata;' in (tmp_path/'spike_effect.h').read_text()
    assert 'rvw_uvm_init(' in (tmp_path/'cpu_top.svh').read_text()
    assert (tmp_path/'image.txt').read_text().startswith('80000000 13\n')


@pytest.mark.parametrize('mutation',[
    lambda i,h,r,e:i.core_run.update(status='timeout'),
    lambda i,h,r,e:i.core_run.update(elf_sha256='wrong'),
    lambda i,h,r,e:i.core_run.update(instret=2),
    lambda i,h,r,e:i.core_run.update(wall_clock_timeout=True),
    lambda i,h,r,e:h.update(schema='rvw.rvfi/2'),
    lambda i,h,r,e:h.update(core='another'),
    lambda i,h,r,e:h.update(isa='rv64i'),
    lambda i,h,r,e:r.update(order=1),
    lambda i,h,r,e:r.update(intr=True),
    lambda i,h,r,e:e.update(status='fail'),
    lambda i,h,r,e:e.update(event='irq',levels='0x0'),
])
def test_reject_incomplete_or_unsupported(capture,tmp_path,mutation):
    inputs,header,row,end,write = capture
    mutation(inputs,header,row,end)
    write()
    with pytest.raises(ValueError):
        uvm_cpu.prepare(inputs,tmp_path)
    assert not (tmp_path/'records.txt').exists()


def test_bad_timeout(tmp_path):
    with pytest.raises(ValueError,match='timeout'):
        uvm_cpu.run(tmp_path/'out',run_dir=tmp_path,elf=tmp_path/'e',platform=tmp_path/'p',
                    archive=tmp_path/'a',timeout=float('nan'))
    assert not (tmp_path/'out').exists()
