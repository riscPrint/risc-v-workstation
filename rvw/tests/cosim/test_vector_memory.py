import copy
import json
from pathlib import Path
import pytest
from rvw.cosim.extensions import header_fields, state_fields, compare_extensions
from test_vh_state import header, state


def memory_state():
    h, row = header(), state()
    h['vector_memory'] = True
    row['vector_accesses'] = [dict(kind='read', address='0x80001000', size=4, data='0x1234')]
    return h, row


def test_ordered_access_mutations():
    h, row = memory_state()
    state_fields(row, h)
    expected = copy.deepcopy(row)
    row['vector_accesses'][0]['data'] = '0x1235'
    assert 'vector_accesses' in compare_extensions(row, expected, h)
    row['vector_accesses'] = []
    assert 'vector_accesses' in compare_extensions(row, expected, h)


@pytest.mark.parametrize('bad', [None, {}, [dict(kind='read', address='0x1', size=3, data='0x0')],
    [dict(kind='write', address='0x1', size=1, data='0x100')]])
def test_invalid_accesses(bad):
    h, row = memory_state()
    row['vector_accesses'] = bad
    with pytest.raises(ValueError):
        state_fields(row, h)


def test_missing_declarations_and_reference():
    h, row = memory_state()
    del row['vector_accesses']
    with pytest.raises(ValueError):
        state_fields(row, h)
    h['vector_memory'] = False
    with pytest.raises(ValueError):
        header_fields(h)
    h, row = memory_state()
    expected = copy.deepcopy(row)
    del expected['vector_accesses']
    with pytest.raises(ValueError, match='reference cannot check'):
        compare_extensions(row, expected, h)


def test_native_vector_load_store_roundtrip(tmp_path, tmp_path_factory):
    from cosim_build import _build
    from rvw.cosim.cli import execute_json
    source = tmp_path/'vector-memory.S'
    source.write_text('''.section .text
.globl _start
_start:
 li t0, 0x600
 csrs mstatus, t0
 li t0, 4
 vsetvli t0, t0, e32, m1, tu, mu
 la a0, data
 vle32.v v1, (a0)
 vadd.vv v2, v1, v1
 vse32.v v2, (a0)
 la t0, tohost
 li t1, 1
 sd t1, (t0)
1: j 1b
.section .data
.balign 16
data: .word 1, 2, 3, 4
.balign 64
.globl tohost
tohost: .dword 0
''')
    elf = _build(tmp_path_factory, source, march='rv64gcv_zicsr_zifencei', mabi='lp64d')
    platform = tmp_path/'platform.json'
    platform.write_text(json.dumps(dict(name='vector',xlen=64,isa='rv64gcv_zicsr_zifencei',
        reset_pc='0x80000000',ram=[dict(base='0x80000000',size='0x1000000')],mmio=[])))
    trace = tmp_path/'trace.jsonl'
    args = dict(core='vector', platform=str(platform), elf=str(elf))
    generated = execute_json('generate', **args, out=str(trace), max_instructions=100)
    assert generated.get('termination') == 'pass', generated
    report = execute_json('check', **args, trace=str(trace), strict=True)
    assert report['status'] == 'match' and report['trace_complete'], report
    rows = [json.loads(line) for line in trace.read_text().splitlines()]
    writes = [a for r in rows for a in r.get('vector_accesses', []) if a['kind'] == 'write']
    assert [int(a['data'],16) for a in writes] == [2,4,6,8]
    target = next(r for r in rows if r.get('vector_accesses'))
    target['vector_accesses'][0]['data'] = '0xff'
    trace.write_text('\n'.join(map(json.dumps,rows))+'\n')
    report = execute_json('check', **args, trace=str(trace), strict=True)
    assert report['status'] == 'mismatch', report
    assert 'vector_accesses' in report['mismatch']['differences']
