"""Native templates must match the shared decoder, including all IMC RVC words."""
import ctypes as C
from dataclasses import asdict
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import pytest
from rvw.ooo import native
from rvw.ooo.core import run
from rvw.common.riscv import decode
from rvw.csim.traces import branch_kind
from rvw.csim.lib import KINDS as BRANCH_KINDS
from test_ooo import cfg,trace

pytestmark=pytest.mark.slow


@pytest.fixture(scope='module')
def library(tmp_path_factory):
    if not shutil.which('cc'):pytest.skip('host C compiler missing')
    return native.build(tmp_path_factory.mktemp('native-decode')/'libooo.so')


def decoder(library):
    lib=C.CDLL(str(library));fn=lib.rvw_ooo_decode_integer
    fn.argtypes=[C.c_uint32,C.c_int,C.c_int,C.POINTER(C.c_int64),C.c_int,C.POINTER(native.Op),C.POINTER(C.c_uint64)]
    return fn


def check(fn,word,rd,xlen,require_complete=False):
    lat=(C.c_int64*7)(1,3,12,4,1,2,2);op=native.Op();meta=(C.c_uint64*2)()
    status=fn(word,rd,xlen,lat,1,C.byref(op),meta)
    d=decode(word,xlen)
    eligible=d.cls in native.KINDS and d.dest_bank=='x' and all(b=='x' for b,_ in d.sources)
    if require_complete:assert (status==0)==eligible,(xlen,hex(word),d)
    if status:return
    assert eligible,(xlen,hex(word),d)
    sources=[r for _,r in d.sources];kind=native.KINDS.index(d.cls)
    assert tuple(getattr(op,k) for k,_ in native.Op._fields_)==(*(sources+[0,0])[:2],rd,lat[kind],kind,0)
    assert meta[0]==d.length
    bk=branch_kind(word,rd,xlen) if d.cls in ('branch','jump') else None
    expected=BRANCH_KINDS[bk or ('cond' if d.cls=='branch' else 'jump')] if d.cls in ('branch','jump') else 0
    assert meta[1]==expected


@pytest.mark.parametrize('xlen',[32,64])
def test_all_compressed_integer_templates(library,xlen):
    fn=decoder(library)
    for word in range(65536):
        if word&3!=3:check(fn,word,word>>7&31,xlen,True)


@pytest.mark.parametrize('xlen',[32,64])
def test_seeded_full_words_do_not_expand_decoder_acceptance(library,xlen):
    fn=decoder(library);rng=random.Random(31)
    for _ in range(20000):check(fn,rng.getrandbits(30)<<2|3,rng.randrange(32),xlen)


def test_full_file_decode_and_compatible_template_fallback(library,tmp_path,monkeypatch):
    monkeypatch.setenv('RVW_OOO_NATIVE',str(library))
    t=tmp_path/'trace';trace(t)
    cp=tmp_path/'config';cp.write_text(json.dumps(asdict(cfg())))
    packed=native.parse_c2(t.read_bytes(),cfg())
    assert packed.decoder=='native-imc'
    assert run(cp,t)['c2_decoder']=='native-imc'
    trace(t,insn='0x60011013')  # CLZ uses the shared bit-manipulation fallback.
    assert native.parse_c2(t.read_bytes(),cfg()).decoder=='python-template'


def test_older_abi2_library_keeps_python_template_path(tmp_path,monkeypatch):
    if not shutil.which('cc'):pytest.skip('host C compiler missing')
    source=Path(native.__file__).with_name('native.c');target=tmp_path/'old.so'
    subprocess.run(['cc','-O3','-std=c11','-fPIC','-dynamiclib' if sys.platform=='darwin' else '-shared',
                    str(source),str(source.with_name('native_c2.c')),'-o',str(target)],check=True)
    monkeypatch.setenv('RVW_OOO_NATIVE',str(target));t=tmp_path/'trace';trace(t)
    assert native.parse_c2(t.read_bytes(),cfg()).decoder=='python-template'
