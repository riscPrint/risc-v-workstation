import ctypes
import json
from pathlib import Path
import random
import shutil
import subprocess
import pytest
from rvw.cli import main
from rvw.formal.datapath_binding import bind

MODELS=Path(__file__).resolve().parents[3]/'SpinalChecks/c2rtl/models'


@pytest.fixture(scope='module')
def library(tmp_path_factory):
    if not shutil.which('clang'):pytest.skip('needs native clang')
    out=tmp_path_factory.mktemp('scalar-ciphers')
    source=out/'models.c'
    lines=['#include "riscv_aes.h"','#include "riscv_sm4.h"','#include "riscv_sha512_split.h"',
           'uint64_t a64(unsigned op,uint64_t a,uint64_t b,unsigned i){return rvw_aes64(op,a,b,i);}',
           'uint32_t a32(unsigned op,uint32_t a,uint32_t b,unsigned i){return rvw_aes32(op,a,b,i);}',
           'uint32_t sm4(unsigned op,uint32_t a,uint32_t b,unsigned i){return rvw_sm4(op,a,b,i);}',
           'uint32_t split(unsigned op,uint32_t a,uint32_t b){return rvw_sha512_split(op,a,b);}',
           'uint8_t sbox(unsigned x,unsigned inv){return rvw_sbox((uint8_t)x,inv);}']
    for file in sorted([*MODELS.glob('aes*.c'),*MODELS.glob('sm4*.c'),*MODELS.glob('sha512s*[hlr].c')]):
        lines += [f'#define reference ref_{file.stem}',f'#include "{file.name}"','#undef reference']
    source.write_text('\n'.join(lines))
    subprocess.run(['clang','-shared','-fPIC','-I',str(MODELS),str(source),'-o',str(out/'models.dylib')],check=True,capture_output=True)
    lib=ctypes.CDLL(str(out/'models.dylib'))
    lib.a64.argtypes=[ctypes.c_uint,ctypes.c_uint64,ctypes.c_uint64,ctypes.c_uint];lib.a64.restype=ctypes.c_uint64
    for name in ('a32','sm4'):
        f=getattr(lib,name);f.argtypes=[ctypes.c_uint,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_uint];f.restype=ctypes.c_uint32
    lib.split.argtypes=[ctypes.c_uint,ctypes.c_uint32,ctypes.c_uint32];lib.split.restype=ctypes.c_uint32
    lib.sbox.argtypes=[ctypes.c_uint,ctypes.c_uint];lib.sbox.restype=ctypes.c_uint8
    return lib


def keys(lib,key):
    rows=[(int.from_bytes(key[:8],'little'),int.from_bytes(key[8:],'little'))]
    for r in range(10):
        a,b=rows[-1];low=lib.a64(5,lib.a64(6,b,0,r),a,0);rows.append((low,lib.a64(5,low,b,0)))
    return rows


def aes(lib,key,data,width,decrypt=False):
    expanded=keys(lib,key);start=10 if decrypt else 0
    rounds=range(9,-1,-1) if decrypt else range(1,11)
    if width==64:
        x=[int.from_bytes(data[:8],'little')^expanded[start][0],int.from_bytes(data[8:],'little')^expanded[start][1]]
        for r in rounds:
            final=(r==0 if decrypt else r==10);op=(2 if final else 3) if decrypt else (0 if final else 1)
            rk=tuple(lib.a64(4,k,0,0) for k in expanded[r]) if decrypt and not final else expanded[r]
            x=[lib.a64(op,x[0],x[1],0)^rk[0],lib.a64(op,x[1],x[0],0)^rk[1]]
        return b''.join(v.to_bytes(8,'little') for v in x)
    x=[int.from_bytes(data[i:i+4],'little') ^ ((expanded[start][i//8]>>(8*(i%8)))&0xffffffff) for i in range(0,16,4)]
    for r in rounds:
        final=(r==0 if decrypt else r==10);op=(2 if final else 3) if decrypt else (0 if final else 1)
        rk=tuple(lib.a64(4,k,0,0) for k in expanded[r]) if decrypt and not final else expanded[r]
        result=[]
        for col in range(4):
            word=(rk[col//2]>>(32*(col%2)))&0xffffffff
            for row in range(4):word=lib.a32(op,word,x[(col+(-row if decrypt else row))%4],row)
            result.append(word)
        x=result
    return b''.join(v.to_bytes(4,'little') for v in x)


VECTORS=[('000102030405060708090a0b0c0d0e0f','00112233445566778899aabbccddeeff','69c4e0d86a7b0430d8cdb78070b4c55a'),
         ('00'*16,'00'*16,'66e94bd4ef8a2c3b884cfa59ca342b2e'),
         ('2b7e151628aed2a6abf7158809cf4f3c','6bc1bee22e409f96e93d7e117393172a','3ad77bb40d7a3660a89ecaf32466ef97')]


@pytest.mark.parametrize('width',[32,64])
@pytest.mark.parametrize('key,plain,cipher',VECTORS)
def test_aes_instruction_composition_known_answers(library,width,key,plain,cipher):
    k,p,c=map(bytes.fromhex,(key,plain,cipher))
    assert aes(library,k,p,width)==c
    assert aes(library,k,c,width,True)==p


def test_aes_substitutions_and_special_key_immediate(library):
    for x in range(256):assert library.sbox(library.sbox(x,0),1)==x
    assert library.a64(6,0x0010203000000000,0,10)==0x63cab70463cab704


def test_aes_against_openssl(library):
    tool=shutil.which('openssl')
    if not tool:pytest.skip('needs OpenSSL CLI')
    rng=random.Random(19)
    for _ in range(20):
        key=rng.randbytes(16);plain=rng.randbytes(16)
        expected=subprocess.run([tool,'enc','-aes-128-ecb','-K',key.hex(),'-nosalt','-nopad'],input=plain,capture_output=True,check=True).stdout
        for width in (32,64):assert aes(library,key,plain,width)==expected


def test_rv32_split_sha512_matches_64bit_transforms(library):
    rng=random.Random(19);mask=(1<<64)-1
    def ror(x,n):return ((x>>n)|(x<<(64-n)))&mask
    for x in [0,1,mask,1<<63]+[rng.getrandbits(64) for _ in range(100)]:
        lo,hi=x&0xffffffff,x>>32
        expected=[ror(x,1)^ror(x,8)^(x>>7),ror(x,19)^ror(x,61)^(x>>6),ror(x,28)^ror(x,34)^ror(x,39),ror(x,14)^ror(x,18)^ror(x,41)]
        actual=[library.split(1,lo,hi)|(library.split(0,hi,lo)<<32),library.split(3,lo,hi)|(library.split(2,hi,lo)<<32),
                library.split(4,lo,hi)|(library.split(4,hi,lo)<<32),library.split(5,lo,hi)|(library.split(5,hi,lo)<<32)]
        assert actual==expected


def test_sm4_instruction_composition_and_sign_extension(library):
    key=bytes.fromhex('0123456789abcdeffedcba9876543210');plain=key
    words=lambda data:[int.from_bytes(data[i:i+4],'little') for i in range(0,16,4)]
    fk=[int.from_bytes(x.to_bytes(4,'big'),'little') for x in [0xa3b1bac6,0x56aa3350,0x677d9197,0xb27022dc]]
    k=[a^b for a,b in zip(words(key),fk)];roundkeys=[]
    for r in range(32):
        ck=int.from_bytes(bytes(((4*r+j)*7)&255 for j in range(4)),'little');value=k[1]^k[2]^k[3]^ck;t=0
        for bs in range(4):t=library.sm4(1,t,value,bs)
        k=k[1:]+[k[0]^t];roundkeys.append(k[-1])
    def crypt(data,keys):
        x=words(data)
        for rk in keys:
            value=x[1]^x[2]^x[3]^rk;t=0
            for bs in range(4):t=library.sm4(0,t,value,bs)
            x=x[1:]+[x[0]^t]
        return b''.join(v.to_bytes(4,'little') for v in reversed(x))
    cipher=crypt(plain,roundkeys)
    assert cipher.hex()=='681edf34d206965e86b3e94f536e4246'
    assert crypt(cipher,list(reversed(roundkeys)))==plain
    for op,name in enumerate(('sm4ed','sm4ks')):
        for bs in range(4):
            f=getattr(library,f'ref_{name}_64_bs{bs}');f.argtypes=[ctypes.c_uint64]*3+[ctypes.c_uint8,ctypes.POINTER(ctypes.c_uint8)];f.restype=ctypes.c_uint64
            for a,b in [(0,0),(0xffffffff,255),(0x80000000,0x80000000)]:
                value=library.sm4(op,a,b,bs);expected=value|0xffffffff00000000 if value>>31 else value
                flags=ctypes.c_uint8(0)
                assert f(a|(0xabcd<<32),b|(0x1234<<32),0,0,ctypes.byref(flags))==expected


def test_constant_bindings_are_explicit_and_do_not_mutate_design():
    design={'modules':{'Unit':{'ports':{'op':{'direction':'input','bits':[7,8]},'a':{'direction':'input','bits':[1]}},
             'cells':{'n':{'connections':{'A':[7,8],'Y':[9]}}},'netnames':{}}}}
    result=bind(design,{'top':'Unit','ports':{},'constants':{'op':2}})
    assert 'op' in design['modules']['Unit']['ports']
    assert 'op' not in result['modules']['dut']['ports']
    assert result['modules']['dut']['cells']['n']['connections']['A']==['0','1']
    with pytest.raises(ValueError):bind(design,{'top':'Unit','ports':{},'constants':{'op':4}})


@pytest.mark.skipif(not all(shutil.which(t) for t in ('yosys','cbmc')),reason='needs Yosys and CBMC')
@pytest.mark.parametrize('selector',[0,1])
def test_symbolic_aes_inverse_mixcolumns_with_constant_opcode(tmp_path,selector):
    rtl='''module Cipher(input [63:0] lhs,rhs,input [1:0] op,output [63:0] result);
function [7:0] xt(input [7:0] x); xt=(x<<1)^(x[7]?8'h1b:8'h00);endfunction
function [7:0] m9(input [7:0] x);m9=xt(xt(xt(x)))^x;endfunction
function [7:0] m11(input [7:0] x);m11=xt(xt(xt(x)))^xt(x)^x;endfunction
function [7:0] m13(input [7:0] x);m13=xt(xt(xt(x)))^xt(xt(x))^x;endfunction
function [7:0] m14(input [7:0] x);m14=xt(xt(xt(x)))^xt(xt(x))^xt(x);endfunction
function [31:0] im(input [31:0] w);reg [7:0] a,b,c,d;begin
 a=w[7:0];b=w[15:8];c=w[23:16];d=w[31:24];
 im[7:0]=m14(a)^m11(b)^m13(c)^m9(d);
 im[15:8]=m9(a)^m14(b)^m11(c)^m13(d);
 im[23:16]=m13(a)^m9(b)^m14(c)^m11(d);
 im[31:24]=m11(a)^m13(b)^m9(c)^m14(d);
end endfunction
assign result=(op==0) ? {im(lhs[63:32]),im(lhs[31:0])} : lhs^rhs;
endmodule'''
    source=tmp_path/'unit.v';source.write_text(rtl)
    binding=tmp_path/'bind.json';binding.write_text(json.dumps({'top':'Cipher','ports':{'a':'lhs','b':'rhs','y':'result'},'constants':{'op':selector}}))
    out=tmp_path/'out'
    main(['formal','datapath','--rtl',str(source),'--model',str(MODELS/'aes64im.c'),'--binding',str(binding),
          '--reference-tree',str(MODELS),'--reference-include','.','--width','64','--out',str(out),'--timeout','90'])
    result=json.loads((out/'result.json').read_text())
    assert result['status']==('proved' if selector==0 else 'counterexample'),result


@pytest.mark.skipif(not all(shutil.which(t) for t in ('yosys','cbmc')),reason='needs Yosys and CBMC')
@pytest.mark.parametrize('uses_unused',[False,True])
def test_unary_binding_adds_unconstrained_reference_argument(tmp_path,uses_unused):
    rtl=tmp_path/'unit.v';rtl.write_text('module Unary(input [63:0] operand,output [63:0] result);assign result=~operand;endmodule')
    model=tmp_path/'reference.c';model.write_text('uint64_t reference(uint64_t a,uint64_t b,uint64_t c,uint8_t rm,uint8_t *flags){return '+('~a^b' if uses_unused else '~a')+';}')
    binding=tmp_path/'bind.json';binding.write_text(json.dumps({'top':'Unary','ports':{'a':'operand','y':'result'},'unused_inputs':{'b':64}}))
    out=tmp_path/'out'
    main(['formal','datapath','--rtl',str(rtl),'--model',str(model),'--binding',str(binding),'--width','64','--out',str(out)])
    result=json.loads((out/'result.json').read_text())
    assert result['status']==('counterexample' if uses_unused else 'proved'),result
