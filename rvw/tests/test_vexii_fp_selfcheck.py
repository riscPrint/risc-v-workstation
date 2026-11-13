import importlib.util
import sys
from pathlib import Path
import pytest
root=Path(__file__).resolve().parents[2]
script=root/'examples/vexiiriscv/rvw/fpu/selfcheck.py'
spec=importlib.util.spec_from_file_location('vexii_selfcheck',script)
m=importlib.util.module_from_spec(spec)
sys.path.insert(0,str(script.parent))
try:spec.loader.exec_module(m)
finally:sys.path.pop(0)
pytestmark=pytest.mark.fast
from rvw.common.riscv import decode

def test_all_plans_keep_the_instruction_and_source_banks():
    for xlen,width in ((32,32),(64,32),(64,64)):
        plan=m.cases(xlen,width,1,1)
        assert plan and any(n.startswith('fmadd') for n in plan)
        for name,entries in plan.items():
            assert len(entries)==35
            assert {e['rm'] for e in entries}==set(range(5))
            for entry in entries:
                d=decode(entry['insn'],xlen)
                assert d.mnemonic==name
                if d.length==4:
                    if d.cls!='store':
                        assert (entry['insn']>>7)&31 == (0 if d.dest_bank=='f' else 28)
                    for pos,reg in enumerate((d.rs1,d.rs2,d.rs3),1):
                        if reg and reg[0]=='f': assert reg[1]==pos

def test_expected_bits_and_flags_are_explicit_checks():
    entries=m.cases(64,32,1,0)['fadd.s'][:1]
    text=m.source(entries,[dict(value=0xffffffff7fc00000,flags=16,fd=0,offset=0)])
    assert 'li t0, 16\n  bne t2, t0, fail' in text
    assert 'fmv.x.w t3, f0' in text and 'li t0, 0x7fc00000' in text
    assert 'csrw fcsr' in text and '.globl fp_case_0' in text

def test_reference_must_export_the_expected_case():
    entry=m.cases(64,32,1,0)['fadd.s'][0]
    row=dict(pc='0x80000000',insn=hex(entry['insn']),trap=False,fd_valid=True,
             fd=0,fd_wdata='0xffffffff7fc00000',fflags='0x10',mem_addr='0x0')
    result=m.expectations([entry],{'fp_case_0':0x80000000,'input_0':0x80001000},[row])
    assert result[0]['value']==0xffffffff7fc00000 and result[0]['flags']==16
    with pytest.raises(ValueError,match='every planned'):
        m.expectations([entry],{'fp_case_0':0x80000000,'input_0':0x80001000},[])
    row['fd_valid']=False
    with pytest.raises(ValueError,match='FP result'):
        m.expectations([entry],{'fp_case_0':0x80000000,'input_0':0x80001000},[row])
