import importlib.util
from pathlib import Path
import pytest
from rvw.cov import fp
pytestmark = pytest.mark.fast

def test_catalog():
    s = fp.catalog(32, 'rv32imafc_zicsr')
    assert {'fmadd.s', 'fcvt.w.s', 'fcvt.s.w', 'c.flw', 'c.fswsp', 'fclass.s', 'feq.s'} <= set(s)
    assert not any('.d' in n or '.l' in n for n in s)
    assert 'c.fld' in fp.catalog(64, 'rv64imafdc')
    assert set(fp.catalog(64,'rv64gc')) == set(fp.catalog(64,'rv64imafdc'))
    assert 'c.flw' not in fp.catalog(64, 'rv64imafdc')
    assert fp.format_width('fcvt.w.d') == 64

def test_fma_inputs():
    rows = [dict(insn='0x13',fd_valid=True,fd=i,fd_wdata=hex(v),fcsr='0x0')
            for i,v in [(1,0xffffffff00000000),(2,0xffffffff00000001),(3,0xffffffff7f800001)]]
    rows += [dict(insn=hex((3 << 27) | (2 << 20) | (1 << 15) | 0x43), fcsr='0x10')]
    r=fp.report(rows,32)
    assert r['observed']==1
    assert {(h['bin'][2],h['bin'][3],h['bin'][4]) for h in r['hits']} == {(1,'zero',16),(2,'subnormal',16),(3,'snan',16)}

def test_flen_and_boxing():
    rows=[dict(insn='0x13',fd_valid=True,fd=1,fd_wdata='0x3f800000',fcsr='0x0'),
          dict(insn=hex((1<<15)|(1<<20)|0x53),fcsr='0x0')]
    assert fp.report(rows,32,flen=32)['hits'][0]['bin'][3]=='normal'
    assert fp.report(rows,32,flen=64)['hits'][0]['bin'][3]=='qnan'

def test_merge_unknown_and_sticky():
    init=dict(insn='0x13',fd_valid=True,fd=1,fd_wdata='0xffffffff3f800000',fcsr='0x0')
    op=dict(insn=hex((1<<15)|(1<<20)|0x53),fcsr='0x1')
    a=fp.report([init,op,op],32,include_holes=False)
    b=fp.report([op],32,include_holes=False)
    r=fp.merge([a,b])
    assert r['unknown_raised_flags']==1 and r['unknown_operands_or_rm']==1
    assert r['observed']==1 and r['traces']==2
    assert r['hit_bins']==2

def test_no_fp_source_and_raw_move():
    i=fp.encodings(64,'rv64imafdc')['fcvt.s.w']
    r=fp.report([dict(insn='0x13',fcsr='0x0'),dict(insn=hex(i),fcsr='0x0')],32)
    assert r['hits'][0]['bin'][2:]==[0,'not_fp',0]
    i=fp.encodings(64,'rv64imafdc')['fmv.x.w'] | (1<<15)
    r=fp.report([dict(insn='0x13',fd_valid=True,fd=1,fd_wdata='0x1',fcsr='0x0'),
                 dict(insn=hex(i),fcsr='0x0')],32)
    assert r['observed']==1 and r['hits'][0]['bin'][3:] == ['subnormal',0]


def test_merge_preserves_independent_trace_count_in_nested_reports():
    rows=[dict(insn='0x13',fd_valid=True,fd=1,fd_wdata='0xffffffff3f800000',fcsr='0x0'),
          dict(insn=hex((1<<15)|(1<<20)|0x53),fcsr='0x0')]
    r=fp.report(rows,32,include_holes=False)
    merged=fp.merge([fp.merge([r,r]),r])
    assert merged['traces']==3 and merged['observed']==3
    assert merged['hit_operand_class_bins']==2
    assert {hit['count'] for hit in merged['hits']}=={3}


def test_moves_do_not_hide_unexpected_flag_changes_or_sticky_flags():
    word=fp.encodings(64,'rv64imafdc')['fmv.x.w'] | (1<<15)
    initial=dict(insn='0x13',fd_valid=True,fd=1,fd_wdata='0x1',fcsr='0x0')
    moved=dict(insn=hex(word),fcsr='0x10')
    result=fp.report([initial,moved,moved],32)
    assert result['hits'][0]['bin'][4]==16
    assert result['unknown_raised_flags']==1
