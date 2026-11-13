import ctypes
import random
import shutil
import subprocess
from pathlib import Path
import json
import pytest
from rvw.cli import main

MODELS = Path(__file__).resolve().parents[3]/'SpinalChecks/c2rtl/models'


@pytest.fixture(scope='module')
def library(tmp_path_factory):
    if not shutil.which('clang'):
        pytest.skip('needs clang')
    out=tmp_path_factory.mktemp('bit-models')
    source=out/'model.c'
    source.write_text('#include "riscv_zb.h"\n#include "riscv_hash.h"\n'
                      'uint64_t zb(unsigned op,unsigned w,uint64_t a,uint64_t b) {return rvw_zb(op,w,a,b);}\n'
                      'uint64_t hash(unsigned op,unsigned w,uint64_t a) {return rvw_hash(op,w,a);}')
    subprocess.run(['clang','-shared','-fPIC','-I',str(MODELS),str(source),'-o',str(out/'models.dylib')],check=True)
    lib=ctypes.CDLL(str(out/'models.dylib'))
    lib.zb.argtypes=[ctypes.c_uint,ctypes.c_uint,ctypes.c_uint64,ctypes.c_uint64];lib.zb.restype=ctypes.c_uint64
    lib.hash.argtypes=[ctypes.c_uint,ctypes.c_uint,ctypes.c_uint64];lib.hash.restype=ctypes.c_uint64
    return lib


@pytest.mark.parametrize('width',[32,64])
def test_bit_models_against_integer_polynomials(library,width):
    rng=random.Random(19);mask=(1<<width)-1
    values=[0,1,2,127,128,32768,mask,mask-1,1<<(width-1)]+[rng.getrandbits(width) for _ in range(25)]
    for a in values:
        for b in values:
            n=b%width
            polynomial=0
            for i in range(width):
                if b&(1<<i): polynomial ^= a*(1<<i)
            signed=lambda x:x-(1<<width) if x&(1<<(width-1)) else x
            rev=int.from_bytes(a.to_bytes(width//8,'little'),'big')
            orcb=int.from_bytes(bytes(255 if x else 0 for x in a.to_bytes(width//8,'little')),'little')
            expected=[a&~b,a|~b,~(a^b),(a<<n)|(a>>(width-n)),(a>>n)|(a<<(width-n)),
                      a.bit_count(),width-a.bit_length(),width if a==0 else (a&-a).bit_length()-1,
                      min(signed(a),signed(b)),max(signed(a),signed(b)),min(a,b),max(a,b),rev,orcb,
                      polynomial,polynomial>>width,polynomial>>(width-1),
                      (a&255)-256 if a&128 else a&255,(a&65535)-65536 if a&32768 else a&65535,a&65535]
            for op,expected_value in enumerate(expected):
                assert library.zb(op,width,a,b)==expected_value&mask,(op,width,a,b)


@pytest.mark.parametrize('width',[32,64])
def test_hash_models_and_rv64_sign_extension(library,width):
    rng=random.Random(20)
    for a in [0,1,0xffffffff,0x80000000,0x123456789abcdef0]+[rng.getrandbits(64) for _ in range(80)]:
        def ror(x,n,w):
            bits=f'{x&((1<<w)-1):0{w}b}'
            return int(bits[-n:]+bits[:-n],2)
        x=a&0xffffffff
        expected=[ror(x,7,32)^ror(x,18,32)^(x>>3),ror(x,17,32)^ror(x,19,32)^(x>>10),
                  ror(x,2,32)^ror(x,13,32)^ror(x,22,32),ror(x,6,32)^ror(x,11,32)^ror(x,25,32),
                  x^ror(x,23,32)^ror(x,15,32),x^ror(x,17,32)^ror(x,9,32)]
        if width==64:
            expected=[x|0xffffffff00000000 if x>>31 else x for x in expected]
            expected += [ror(a,1,64)^ror(a,8,64)^(a>>7),ror(a,19,64)^ror(a,61,64)^(a>>6),
                         ror(a,28,64)^ror(a,34,64)^ror(a,39,64),ror(a,14,64)^ror(a,18,64)^ror(a,41,64)]
        for op,value in enumerate(expected): assert library.hash(op,width,a)==value


@pytest.mark.skipif(not all(shutil.which(t) for t in ('yosys','cbmc')),reason='needs Yosys and CBMC')
@pytest.mark.parametrize('kind,mutant',[('andn',False),('andn',True),('sha256sig0',False),('sha256sig0',True)])
def test_models_against_symbolic_rtl(tmp_path,kind,mutant):
    expr='a & ~b' if kind=='andn' else '({a[6:0],a[31:7]} ^ {a[17:0],a[31:18]} ^ (a>>3))'
    if mutant: expr=f'({expr}) ^ 1'
    rtl=tmp_path/'dut.v';rtl.write_text(f'module dut(input [31:0] a,b,output [31:0] y); assign y={expr}; endmodule')
    model=MODELS/('andn32.c' if kind=='andn' else 'sha256sig0_32.c')
    out=tmp_path/'out'
    main(['formal','datapath','--rtl',str(rtl),'--model',str(model),'--reference-tree',str(MODELS),'--reference-include','.',
          '--width','32','--out',str(out),'--timeout','60'])
    result=json.loads((out/'result.json').read_text())
    assert result['status']==('counterexample' if mutant else 'proved'),result
