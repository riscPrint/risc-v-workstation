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


def test_online_same_comparison_and_stops(tmp_path):
    from rvw.cosim.online import check_online
    h, row = fixture()
    row['fd_wdata'] = '0x1'
    end = dict(event='end', cycle=2, status='pass')
    lines = [json.dumps(r)+'\n' for r in (h, row, end)]
    stopped = []
    identity = dict(elf_sha256='a', platform_sha256='b', capture={}, tools={})
    online = check_online(iter(lines), Model(fixture()[1]), Platform.load('boom'),
                          stop=lambda: stopped.append(True), reproduction=identity)
    offline = run(tmp_path, row)
    assert online['mismatch'] == offline['mismatch']
    assert online['recent_synchronizations'] == offline['recent_synchronizations']
    assert stopped == [True]
    assert online['reproduction'] == identity


def test_online_complete_and_incomplete():
    from rvw.cosim.online import check_online
    h, row = fixture()
    identity = dict(elf_sha256='a', platform_sha256='b', capture={}, tools={})
    for ended in (False, True):
        records = [h, row] + ([dict(event='end', cycle=2, status='pass')] if ended else [])
        result = check_online(iter(json.dumps(r)+'\n' for r in records), Model(row),
                              Platform.load('boom'), stop=lambda: None, reproduction=identity)
        assert result['status'] == ('match' if ended else 'inconclusive')


def test_online_parse_error_stops():
    from rvw.cosim.online import check_online
    stopped = []
    with pytest.raises(ValueError):
        check_online(iter(['bad\n']), Model(fixture()[1]), Platform.load('boom'),
                     stop=lambda: stopped.append(True),
                     reproduction=dict(elf_sha256='a', platform_sha256='b', capture={}, tools={}))
    assert stopped == [True]


def test_live_producer_is_stopped():
    import subprocess
    import sys
    from rvw.common.proc import kill_group
    from rvw.cosim.online import check_online
    h, row = fixture()
    row['fd_wdata'] = '0x1'
    records = [h, row, dict(event='end', cycle=2, status='pass')]
    text = ''.join(json.dumps(r)+'\n' for r in records)
    code = 'import sys,time; sys.stdout.write('+repr(text)+'); sys.stdout.flush(); time.sleep(60)'
    process = subprocess.Popen([sys.executable, '-c', code], stdout=subprocess.PIPE,
                               text=True, start_new_session=True)
    try:
        result = check_online(process.stdout, Model(fixture()[1]), Platform.load('boom'),
                              stop=lambda: kill_group(process),
                              reproduction=dict(elf_sha256='a', platform_sha256='b', capture={}, tools={}))
        assert result['status'] == 'mismatch'
        assert process.poll() is not None
    finally:
        kill_group(process)
        process.stdout.close()


def test_native_fp_state(tmp_path, tmp_path_factory):
    from cosim_build import _build
    from model_fixtures import Spike
    from rvw.cosim.trace import record
    source = tmp_path / 'fp.S'
    source.write_text('''
.section .text
.globl _start
_start:
  li t0, 0x6000
  csrs mstatus, t0
  li t0, 0x3f800000
  fmv.w.x f0, t0
  fmv.w.x f1, zero
  fdiv.s f2, f0, f1
  csrrwi zero, frm, 3
  fdiv.s f3, f1, f1
  nop
''')
    elf = _build(tmp_path_factory, source, march='rv64imafdc_zicsr')
    platform = Platform.load('boom')
    model = Spike(platform, elf)
    h, _ = fixture()
    h['csr_snapshot'] = ['0x300']
    rows, fp = [], []
    try:
        for order in range(10):
            effect = model.step()
            row = record(effect, order)
            row.update(fd_valid=bool(effect['fd_valid']), fd=effect['fd'],
                       **{k: hex(effect[k]) for k in ('fd_wdata', 'fflags', 'fcsr')})
            row['csr_state'] = {k: hex(v) for k, v in model.csr_snapshot(['0x300']).items()}
            rows.append(row)
            if effect['fd_valid']:
                fp.append(effect)
    finally:
        model.close()
    assert fp[0]['fd'] == 0 and fp[0]['fd_wdata'] == 0xffffffff3f800000
    assert fp[2]['fd_wdata'] == 0xffffffff7f800000 and fp[2]['fflags'] == 8
    assert fp[3]['fd_wdata'] == 0xffffffff7fc00000 and fp[3]['fflags'] == 24
    assert fp[3]['fcsr'] == 0x78  # rounding mode 3 plus accrued DZ/NV
    path = tmp_path / 'native.jsonl'
    path.write_text(''.join(json.dumps(r)+'\n' for r in [h, *rows]))
    model = Spike(platform, elf)
    try:
        assert check(path, model, platform)['status'] == 'match'
    finally:
        model.close()


@pytest.mark.parametrize('key,value', [('rmask', 7), ('wmask', 1)])
def test_fault_mask_mutation(tmp_path, key, value):
    h, row, model = fault_fixture()
    row['fault_access'][key] = value
    assert f'fault_access.{key}' in run(tmp_path, row, model, h)['mismatch']['differences']


def test_fault_backend_limit(tmp_path):
    h, row, model = fault_fixture()
    model.name = 'sail'
    with pytest.raises(ValueError, match='cannot check fault-access'):
        run(tmp_path, row, model, h)


def test_live_digest_covers_consumed_lookahead():
    import hashlib
    from rvw.cosim.online import check_online
    h, row = fixture()
    text = ''.join(json.dumps(r)+'\n' for r in [h, row, dict(event='end', cycle=2, status='pass')])
    result = check_online(iter(text.splitlines(keepends=True)), Model(row), Platform.load('boom'),
                          stop=lambda: None,
                          reproduction=dict(elf_sha256='a', platform_sha256='b', capture={}, tools={}))
    assert result['consumed_trace_prefix_sha256'] == hashlib.sha256(text.encode()).hexdigest()
    assert result['consumed_trace_lines'] == 3


def test_trap_only_trace_does_not_claim_fp_comparison(tmp_path):
    h, row = fixture()
    model = Model(row)
    model.effect.update(trap=True, intr=False, cause=5, tval=0)
    path = tmp_path / 'trap-only.jsonl'
    path.write_text(json.dumps(h)+'\n'+json.dumps(dict(event='trap', cycle=1, cause='0x5', tval='0x0', intr=False))+'\n')
    result = check(path, model, Platform.load('boom'))
    assert result['status'] == 'match'
    assert not result['state_coverage']['fp']
