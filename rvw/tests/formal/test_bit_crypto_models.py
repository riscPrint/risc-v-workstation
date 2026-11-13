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


@pytest.mark.parametrize('width',[32,64])
def test_single_bit_shift_add_permutation_and_pack_models(library,width):
    rng=random.Random(21);mask=(1<<width)-1
    values=[0,1,2,31,32,63,64,127,128,32768,mask,mask-1,1<<(width-1),0x01234567&mask,
            0x76543210&mask,0x0706050403020100&mask]+[rng.getrandbits(width) for _ in range(15)]
    def xperm(a,b,size):
        elements=[(a>>i)&((1<<size)-1) for i in range(0,width,size)]
        indices=[(b>>i)&((1<<size)-1) for i in range(0,width,size)]
        return sum((elements[index] if index<len(elements) else 0)<<pos for index,pos in zip(indices,range(0,width,size)))
    for a in values:
        for b in values:
            n=b%width;half_mask=(1<<(width//2))-1
            reverse_bytes=bytes(int(f'{byte:08b}'[::-1],2) for byte in a.to_bytes(width//8,'little'))
            expected={20:a|(1<<n),21:a&~(1<<n),22:a^(1<<n),23:(a>>n)&1,
                      24:a*2+b,25:a*4+b,26:a*8+b,27:xperm(a,b,4),28:xperm(a,b,8),
                      29:(a&half_mask)|((b&half_mask)<<(width//2)),30:(a&255)|((b&255)<<8),
                      31:int.from_bytes(reverse_bytes,'little')}
            if width==32:
                even=sum(((a>>i)&1)<<(2*i) for i in range(16));odd=sum(((a>>(i+16))&1)<<(2*i+1) for i in range(16))
                expected[32]=even|odd
                expected[33]=sum(((a>>(2*i))&1)<<i for i in range(16))|sum(((a>>(2*i+1))&1)<<(i+16) for i in range(16))
            for op,result in expected.items():assert library.zb(op,width,a,b)==result&mask,(op,width,a,b)
    if width==32:
        assert library.zb(32,32,0xffff,0)==0x55555555
        assert library.zb(32,32,0xffff0000,0)==0xaaaaaaaa


def test_rv64_word_and_unsigned_word_models(library):
    rng=random.Random(22);mask=(1<<64)-1
    values=[0,1,31,32,63,64,0xffffffff,0x80000000,0x8000000000000000,0xffffffffffffffff]+[rng.getrandbits(64) for _ in range(20)]
    def sign_extend(value):return value|0xffffffff00000000 if value&(1<<31) else value
    for a in values:
        for b in values:
            x=a&0xffffffff;n=b%32
            left=((x<<n)|(x>>(32-n)))&0xffffffff
            right=((x>>n)|(x<<(32-n)))&0xffffffff
            expected={34:x+b,35:x*2+b,36:x*4+b,37:x*8+b,38:x<<(b%64),
                      39:sign_extend(left),40:sign_extend(right),41:x.bit_count(),42:32-x.bit_length(),
                      43:32 if x==0 else (x&-x).bit_length()-1,
                      44:sign_extend((a&65535)|((b&65535)<<16))}
            for op,result in expected.items():assert library.zb(op,64,a,b)==result&mask,(op,a,b)


@pytest.mark.skipif(not all(shutil.which(t) for t in ('yosys','cbmc')),reason='needs native Yosys and CBMC')
@pytest.mark.parametrize('width,size,mutant',[(32,4,False),(32,4,True),(64,8,False),(64,8,True)])
def test_symbolic_xperm_unit(tmp_path,width,size,mutant):
    source=tmp_path/'dut.v'
    expression=f'a >> ((selector+{1 if mutant else 0})*{size})'
    source.write_text(f'module dut(input [{width-1}:0] a,b,output [{width-1}:0] y);genvar i;generate for(i=0;i<{width//size};i=i+1)begin:perm '
                      f'wire [{size-1}:0] selector=b[i*{size}+:{size}];assign y[i*{size}+:{size}]=(selector<{width//size}) ? ({expression}) : 0;end endgenerate endmodule')
    out=tmp_path/'out'
    main(['formal','datapath','--rtl',str(source),'--model',str(MODELS/f'xperm{size}{width}.c'),
          '--reference-tree',str(MODELS),'--reference-include','.','--width',str(width),'--out',str(out),'--timeout','90'])
    result=json.loads((out/'result.json').read_text())
    assert result['status']==('counterexample' if mutant else 'proved'),result
