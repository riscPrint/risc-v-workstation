import asyncio
import json
import pytest
from rvw.uvm.csr_sequence import CsrQualification


def selection(tmp_path, **extra):
    row = dict(name='mscratch', reset=17, assembly_safe=True,
        fields=[dict(name='SCRATCH', access=dict(U='RO', S='RO', M='RW'))], **extra)
    p = tmp_path/'csr.json'
    p.write_text(json.dumps(dict(schema='rvw.csr-selection/1',xlen=32,csrs=[row])))
    return p


def test_catalog_sequence_and_restore(tmp_path):
    path = selection(tmp_path)
    state, writes = 17, []
    async def execute(address, t):
        nonlocal state
        assert address == 0x340
        old = state
        if t['write']:
            state = t['data']; writes.append(state)
        return dict(trap=False, read_data=old)
    report = asyncio.run(CsrQualification(path).run(execute, random_writes=3))
    assert state == 17
    assert len(writes) == 38
    assert report['checks'] == 77
    assert report['coverage'] == [('mscratch','read',False),('mscratch','write',False)]


@pytest.mark.parametrize('fault', ['read', 'trap'])
def test_faults_fail(tmp_path, fault):
    async def execute(address, t):
        return dict(trap=fault == 'trap', read_data=18)
    with pytest.raises(AssertionError, match='CSR_DATA' if fault == 'read' else 'CSR_TRAP'):
        asyncio.run(CsrQualification(selection(tmp_path)).run(execute))


def test_unknown_reset_is_initialized_before_read(tmp_path):
    path = selection(tmp_path, reset_known=False)
    state, first = 0xdeadbeef, True
    async def execute(address, t):
        nonlocal state, first
        if first:
            assert t['write'] and not t['read']; first = False
        old = state
        if t['write']: state = t['data']
        return dict(trap=False, read_data=old)
    asyncio.run(CsrQualification(path).run(execute, random_writes=0))
    assert state == 17


def test_absent_csr_requires_illegal_instruction_result(tmp_path):
    p = tmp_path/'absent.json'
    p.write_text(json.dumps(dict(schema='rvw.csr-selection/1',xlen=32,
        csrs=[dict(name='sscratch',reset=0,present=False)])))
    async def execute(address, t):
        assert address == 0x140
        return dict(trap=True)
    report = asyncio.run(CsrQualification(p).run(execute))
    assert report['checks'] == 1


def test_writes_require_project_opt_in(tmp_path):
    p = selection(tmp_path)
    obj = json.loads(p.read_text()); obj['csrs'][0]['assembly_safe'] = False
    p.write_text(json.dumps(obj))
    async def execute(address, t):
        assert t['read'] and not t['write']
        return dict(trap=False,read_data=17)
    assert asyncio.run(CsrQualification(p).run(execute))['checks'] == 1
