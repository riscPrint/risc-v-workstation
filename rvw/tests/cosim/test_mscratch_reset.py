"""Only unspecified mscratch reset bits can come from the DUT."""
import copy
import json
import pytest
from rvw.cosim.checker import check
from rvw.cosim.platform import Platform
from rvw.cosim.trace import record


class Model:
    name = 'fixture'

    def __init__(self, program, initial=0):
        self.program, self.index, self.scratch = program, 0, initial
        self.regs = [0] * 32
        self.regs[1] = 2

    def set_mscratch(self, value):
        self.scratch = value

    def set_reg(self, rd, value):
        self.regs[rd] = value

    def csr_snapshot(self, addresses):
        return {'0x340': self.scratch}

    def step(self, **kwargs):
        op, rd, source = self.program[self.index]
        pc = 0x80000000 + self.index * 4
        before, old = list(self.regs), self.scratch
        value = source if op >= 5 else self.regs[source]
        if op in (1, 5):
            self.scratch = value
        elif op in (2, 6):
            self.scratch |= value
        else:
            self.scratch &= ~value
        if rd:
            self.regs[rd] = old
        self.index += 1
        return dict(pc=pc, pc_next=pc+4, insn=(0x340<<20)|(source<<15)|(op<<12)|(rd<<7)|0x73,
                    mode=3, rd=rd, rd_wdata=old if rd else 0, rs1=source if op<5 else 0, rs2=0,
                    rs1_rdata=before[source] if op<5 else 0, rs2_rdata=0,
                    mem_addr=0, mem_rmask=0, mem_wmask=0, mem_rdata=0, mem_wdata=0,
                    trap=False, intr=False, mem_fault=False, regs=list(self.regs), before=before,
                    disasm='CSR fixture', fd_valid=False, fd=0, fd_wdata=0, fflags=0, fcsr=0)


def run(tmp_path, program, *, mutate=None, sync=('csr',), reset=True, snapshot=False):
    platform = copy.copy(Platform.load('boom'))
    platform.trace_from_reset = reset
    dut = Model(program, initial=7)
    rows = [dict(schema='rvw.rvfi/1', xlen=64, isa=platform.isa, core='fixture', config='test', elf='fixture')]
    if snapshot:
        rows[0]['schema'] = 'rvw.rvfi/2'
        rows[0]['csr_snapshot'] = ['0x340']
    for index in range(len(program)):
        effect = dut.step()
        row = record(effect, index)
        if snapshot:
            row.update(fd_valid=False, fd=0, fd_wdata='0x0', fflags='0x0', fcsr='0x0')
            row['csr_state'] = {'0x340': hex(dut.scratch)}
        rows.append(row)
    if mutate:
        mutate(rows)
    path = tmp_path/'trace.jsonl'
    path.write_text('\n'.join(map(json.dumps, rows))+'\n')
    return check(path, Model(program), platform, sync=sync)


@pytest.mark.parametrize('op', [1, 2, 3, 5, 6, 7])
def test_initial_read_is_recorded_then_checked(tmp_path, op):
    result = run(tmp_path, [(op, 2, 1), (2, 3, 0)])
    assert result['status'] == 'match', result
    entries = result['recent_synchronizations']
    assert len(entries) == 1
    assert entries[0]['reason'] == 'csr_reset_unknown'
    assert entries[0]['csr'] == '0x340'
    assert entries[0]['mask'] == '0xffffffffffffffff'


def test_later_wrong_read_is_not_synchronized(tmp_path):
    result = run(tmp_path, [(2, 2, 0), (2, 3, 0)],
                 mutate=lambda rows: rows[2].update(rd_wdata='0x6'))
    assert result['status'] == 'mismatch'
    assert result['mismatch']['instruction_index'] == 1


@pytest.mark.parametrize('op', [1, 5])
def test_write_before_read_removes_reset_unknown(tmp_path, op):
    result = run(tmp_path, [(op, 0, 1), (2, 3, 0)],
                 mutate=lambda rows: rows[2].update(rd_wdata='0x7'))
    assert result['status'] == 'mismatch'
    assert result['synchronized'] == 0


@pytest.mark.parametrize('op', [2, 3, 6, 7])
def test_partial_write_keeps_written_bits_strict(tmp_path, op):
    program = [(op, 0, 1), (2, 3, 0)]
    assert run(tmp_path, program)['status'] == 'match'
    bit = 2 if op < 5 else 1
    result = run(tmp_path, program, mutate=lambda rows: rows[2].update(
        rd_wdata=hex(int(rows[2]['rd_wdata'], 16) ^ bit)))
    assert result['status'] == 'mismatch'


@pytest.mark.parametrize('kwargs', [{'sync': ()}, {'reset': False}])
def test_disabled_or_nonreset_trace_stays_strict(tmp_path, kwargs):
    assert run(tmp_path, [(2, 2, 0)], **kwargs)['status'] == 'mismatch'


def test_structural_mismatch_cannot_be_hidden(tmp_path):
    result = run(tmp_path, [(2, 2, 0)], mutate=lambda rows: rows[1].update(pc_next='0x80000008'))
    assert result['status'] == 'mismatch'


def test_snapshot_observation_is_recorded(tmp_path):
    result = run(tmp_path, [(2, 0, 0), (2, 3, 0)], snapshot=True)
    assert result['status'] == 'match', result
    assert result['synchronized'] == 1
    assert result['recent_synchronizations'][0]['source'] == 'csr_state'


def test_missing_model_support_is_an_error(tmp_path, monkeypatch):
    monkeypatch.delattr(Model, 'set_mscratch')
    with pytest.raises(ValueError, match='cannot synchronize'):
        run(tmp_path, [(2, 2, 0)])


@pytest.mark.parametrize('op', [1, 5])
def test_full_write_then_read_needs_no_sync(tmp_path, op):
    result = run(tmp_path, [(op, 0, 1), (2, 3, 0)])
    assert result['status'] == 'match'
    assert result['synchronized'] == 0


@pytest.mark.parametrize('first', ['csrrw t1,mscratch,t0', 'csrrs t1,mscratch,t0',
                                   'csrrc t1,mscratch,t0', 'csrrsi t1,mscratch,2'])
def test_native_spike_reset_state_and_later_read(tmp_path, tmp_path_factory, platform, first):
    from cosim_build import _build
    from model_fixtures import Spike
    source = tmp_path/'scratch.S'
    source.write_text('.section .text.init\n.globl _start\n_start:\nli t0,2\n' + first +
                      '\ncsrr t2,mscratch\ncsrw mscratch,t0\ncsrr t3,mscratch\n'
                      'la t0,tohost\nli t1,1\nsd t1,0(t0)\n1: j 1b\n'
                      '.section .tohost,"aw"\n.balign 8\n.globl tohost\ntohost: .dword 0\n')
    elf = _build(tmp_path_factory, source)
    dut = Spike(platform, elf)
    rows = [dict(schema='rvw.rvfi/1', xlen=64, isa=platform.isa, core='fixture', config='test', elf=str(elf))]
    try:
        dut.set_mscratch(0xa7c3545262201bf1)
        for index in range(30):
            effect = dut.step()
            rows.append(record(effect, index))
            if effect['mem_wmask'] and effect['mem_addr'] == dut.elf.symbols['tohost']:
                rows.append(dict(event='end', cycle=index+1, status='pass'))
                break
        else:
            pytest.fail('native program did not terminate')
    finally:
        dut.close()
    path = tmp_path/'native.jsonl'
    path.write_text('\n'.join(map(json.dumps, rows))+'\n')
    reference = Spike(platform, elf)
    try:
        result = check(path, reference, platform)
    finally:
        reference.close()
    assert result['status'] == 'match', result
    assert result['trace_complete'] and result['end_status'] == 'pass'
    assert result['synchronized'] == 1
    assert result['recent_synchronizations'][0]['csr'] == '0x340'


def test_snapshot_without_backend_support_is_an_error(tmp_path, monkeypatch):
    monkeypatch.delattr(Model, 'csr_snapshot')
    with pytest.raises(ValueError, match='cannot check CSR snapshots'):
        run(tmp_path, [(2, 0, 0)], snapshot=True)
