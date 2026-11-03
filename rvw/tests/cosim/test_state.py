"""C2 state evidence: exact data, optional backend support, no DUT seeding."""
import copy
import json
import pytest
from rvw.cosim.checker import check
from rvw.cosim.platform import Platform


def fixture():
    row = dict(order=0, cycle=1, mode=3, trap=False, intr=False, halt=False,
               mem_fault=False, rs1=0, rs2=0, rd=0, mem_rmask=0, mem_wmask=0,
               fd_valid=True, fd=0)
    row.update({k: '0x0' for k in 'pc pc_next insn rs1_rdata rs2_rdata rd_wdata mem_addr mem_rdata mem_wdata fd_wdata fflags fcsr'.split()})
    row.update(pc='0x80000000', pc_next='0x80000004', insn='0x13',
               fd_wdata='0xffffffff7fc00000')
    header = dict(schema='rvw.rvfi/2', xlen=64, isa=Platform.load('boom').isa,
                  core='synthetic', config='test', elf='fixture')
    return header, row


class Model:
    def __init__(self, row):
        self.effect = {k: int(v, 16) if isinstance(v, str) else v for k, v in row.items()}
        self.effect.update(regs=[0]*32, disasm='fixture')
    def step(self, **kwargs):
        return copy.deepcopy(self.effect)


def run(tmp_path, row, model=None, header=None):
    h, default = fixture()
    path = tmp_path / 'trace.jsonl'
    path.write_text('\n'.join(map(json.dumps, [header or h, row])))
    return check(path, model or Model(default), Platform.load('boom'))


@pytest.mark.parametrize('value', ['0xffffffff7fc00000', '0x7ff8000000000001', '0xffffffff80000000'])
def test_fp_bits(tmp_path, value):
    _, row = fixture()
    row['fd_wdata'] = value
    assert run(tmp_path, row, Model(row))['status'] == 'match'
    row['fd_wdata'] = hex(int(value, 16)^1)
    assert 'fd_wdata' in run(tmp_path, row)['mismatch']['differences']


@pytest.mark.parametrize('field,value', [('fd', 1), ('fd_valid', False), ('fflags', '0x1'), ('fcsr', '0x20')])
def test_state_mutations(tmp_path, field, value):
    _, row = fixture()
    row[field] = value
    if field == 'fflags':
        row['fcsr'] = value
    assert field in run(tmp_path, row)['mismatch']['differences']


def test_unsupported_backend(tmp_path):
    _, row = fixture()
    model = Model(row)
    del model.effect['fcsr']
    with pytest.raises(ValueError, match='cannot check'):
        run(tmp_path, row, model)


def test_invalid_flags(tmp_path):
    _, row = fixture()
    row['fflags'] = '0x1'
    with pytest.raises(ValueError, match='disagree'):
        run(tmp_path, row)


def test_unread_csr(tmp_path):
    h, row = fixture()
    h['csr_snapshot'] = ['0x300']
    row['csr_state'] = {'0x300': '0x6000'}
    model = Model(row)
    model.csr_snapshot = lambda addresses: {'0x300': 0x6000}
    assert run(tmp_path, row, model, h)['status'] == 'match'
    row['csr_state']['0x300'] = '0x0'
    assert 'csr[0x300]' in run(tmp_path, row, model, h)['mismatch']['differences']


def test_missing_csr_snapshot(tmp_path):
    h, row = fixture()
    h['csr_snapshot'] = ['0x300']
    with pytest.raises(ValueError, match='exactly'):
        run(tmp_path, row, header=h)


def test_backend_cannot_snapshot(tmp_path):
    h, row = fixture()
    h['csr_snapshot'] = ['0x300']
    row['csr_state'] = {'0x300': '0x0'}
    with pytest.raises(ValueError, match='cannot check CSR'):
        run(tmp_path, row, header=h)


def fault_fixture():
    h, row = fixture()
    row.update(trap=True, mem_fault=True, fd_valid=False, insn='0x2083')
    row['fault_access'] = dict(addr='0x0', rmask=15, wmask=0,
                              completed_rmask=0, completed_wmask=0, rdata=None, wdata=None)
    model = Model(row)
    model.effect.update(cause=5, before=[0]*32, intr=False)
    return h, row, model


def test_fault_attempt(tmp_path):
    h, row, model = fault_fixture()
    assert run(tmp_path, row, model, h)['status'] == 'match'
    row['fault_access']['addr'] = '0x4'
    assert 'fault_access.addr' in run(tmp_path, row, model, h)['mismatch']['differences']


def test_fault_partial_refused(tmp_path):
    h, row, model = fault_fixture()
    row['fault_access'].update(completed_rmask=1, rdata='0x0')
    with pytest.raises(ValueError, match='partial fault'):
        run(tmp_path, row, model, h)


def test_unknown_fault_data_not_filled(tmp_path):
    h, row, model = fault_fixture()
    row['fault_access']['rdata'] = '0x0'
    with pytest.raises(ValueError, match='must be null'):
        run(tmp_path, row, model, h)
