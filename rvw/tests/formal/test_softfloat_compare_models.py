import ctypes
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import pytest
from rvw.cli import main

ROOT=Path(__file__).resolve().parents[3]/'SpinalChecks/c2rtl'
SOFTFLOAT=os.environ.get('RVW_TEST_SOFTFLOAT')
pytestmark=pytest.mark.skipif(not SOFTFLOAT, reason='set RVW_TEST_SOFTFLOAT to the pinned external source tree')


def prepare(operation):
    spec=importlib.util.spec_from_file_location('rvw_softfloat_helper',ROOT/'softfloat.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    return helper.prepare(SOFTFLOAT,operation)


@pytest.mark.parametrize('width',[32,64])
@pytest.mark.parametrize('operation',['eq','lt','le'])
def test_native_softfloat_comparison_bits_and_flags(tmp_path,width,operation):
    if not shutil.which('clang'): pytest.skip('needs clang')
    args=prepare(f'f{width}_{operation}')
    root=Path(SOFTFLOAT)
    sources=[str(root/args[i+1]) for i,x in enumerate(args) if x=='--reference-source']
    includes=[str(root/args[i+1]) for i,x in enumerate(args) if x=='--reference-include']
    library=tmp_path/'compare.dylib'
    subprocess.run(['clang','-shared','-fPIC',str(ROOT/f'models/f{width}_{operation}.c'),*sources,
                    *[a for p in includes for a in ('-I',p)],'-o',str(library)],check=True,capture_output=True)
    function=ctypes.CDLL(str(library)).reference
    function.argtypes=[ctypes.c_uint64]*3+[ctypes.c_uint8,ctypes.POINTER(ctypes.c_uint8)];function.restype=ctypes.c_uint64
    fraction=23 if width==32 else 52;exponent=8 if width==32 else 11
    sign=1<<(width-1);mask=(1<<width)-1;exp=((1<<exponent)-1)<<fraction;quiet=1<<(fraction-1)
    values=[0,sign,1,sign|1,exp,sign|exp,exp|quiet,exp|1,exp|quiet|1,(exp-1),sign|(exp-1)]
    def nan(x):return x&exp==exp and bool(x&((1<<fraction)-1))
    def snan(x):return nan(x) and not x&quiet
    def key(x):return (~x)&mask if x&sign else x^sign
    for a in values:
        for b in values:
            unordered=nan(a) or nan(b)
            eq=(a==b or ((a&~sign)==0 and (b&~sign)==0)) and not unordered
            lt=not unordered and not eq and key(a)<key(b)
            expected={'eq':eq,'lt':lt,'le':eq or lt}[operation]
            flags=ctypes.c_uint8(255)
            assert function(a,b,0,0,ctypes.byref(flags))==expected
            assert flags.value==(16 if snan(a) or snan(b) or (operation!='eq' and unordered) else 0)


@pytest.mark.skipif(not all(shutil.which(t) for t in ('yosys','cbmc')),reason='needs Yosys and CBMC')
@pytest.mark.parametrize('mutant',[False,True])
def test_symbolic_f32_eq_and_invalid_flag(tmp_path,mutant):
    rtl=tmp_path/'dut.v'
    invalid='0' if mutant else '(sa|sb)'
    rtl.write_text('module dut(input [31:0] a,b,output [31:0] y,output [4:0] flags); '
                   'wire na=(&a[30:23]) && (|a[22:0]); wire nb=(&b[30:23]) && (|b[22:0]); '
                   'wire sa=na && !a[22];wire sb=nb && !b[22]; '
                   'assign y=!(na|nb) && ((a==b) || ((a[30:0]==0)&&(b[30:0]==0))); '
                   'assign flags={'+invalid+",4'b0}; endmodule")
    out=tmp_path/'out'
    main(['formal','datapath','--rtl',str(rtl),'--model',str(ROOT/'models/f32_eq.c'),'--width','32',
          *prepare('f32_eq'),'--out',str(out),'--timeout','90'])
    result=json.loads((out/'result.json').read_text())
    assert result['status']==('counterexample' if mutant else 'proved'),result
