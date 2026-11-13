"""N-Trace codec, decoder, checks, loss campaign and vendor adapters (no native tools)."""
import json
from pathlib import Path

import pytest

from rvw.debug import ntrace, ntrace_check as nc, api
from rvw.debug.hart import Asm, Hart, Memory

ROOT = Path(__file__).resolve().parents[2]
BASE = 0x80000000
S0, S1, T0 = 8, 9, 5


def program():
    """Branches, an M-mode ecall to a handler that returns, then mret to U-mode and a U ecall."""
    handler = 0x80
    user = 0x60
    words = [
        Asm.auipc(T0, 0), Asm.addi(T0, T0, handler), Asm.csrrw(0, 0x305, T0),  # mtvec
        Asm.addi(S0, 0, 4),                    # 0x0c
        Asm.addi(S0, S0, -1),                  # 0x10 loop
        Asm.addi(6, S0, -2),                   # 0x14
        Asm.bne(6, 0, 8),                      # 0x18 -> 0x20 unless s0 == 2
        Asm.ECALL,                             # 0x1c
        Asm.bne(S0, 0, -0x10),                 # 0x20 -> 0x10
        Asm.auipc(T0, 0), Asm.addi(T0, T0, user - 0x24), Asm.csrrw(0, 0x341, T0),  # 0x24: mepc = user
        Asm.addi(T0, 0, 0), Asm.lui(T0, 2), Asm.addi(T0, T0, -2048),   # t0 = 0x1800
        Asm.csrrs(0, 0x300, 0), 0x3002b073,     # csrc mstatus, t0 (MPP = U)
        Asm.MRET,                               # 0x48 .. padded below
    ]
    words += [Asm.NOP] * ((user // 4) - len(words))
    words += [Asm.addi(S1, 0, 2), Asm.addi(S1, S1, -1), Asm.ECALL, Asm.bne(S1, 0, -8), Asm.j(0)]
    words += [Asm.NOP] * ((handler // 4) - len(words))
    words += [Asm.csrrs(7, 0x341, 0), Asm.addi(7, 7, 4), Asm.csrrw(0, 0x341, 7), Asm.MRET]
    return words, BASE + user + 0x10


def run_c2(path, steps=200):
    words, done = program()
    memory = Memory([{'base': BASE, 'size': 0x1000}])
    image = Asm.words(*words)
    memory.load(BASE, image)
    hart = Hart(memory, reset_pc=BASE, modes='MU')
    taken = []
    original = hart.take_trap
    hart.take_trap = lambda cause, tval, pc: (taken.append((cause, tval)), original(cause, tval, pc))[1]
    records = [dict(schema='rvw.rvfi/1', xlen=64, isa='rv64i', core='model', config='t', elf='t')]
    order = 0
    previous_trap = False
    while order < steps:
        pc, mode = hart.pc, hart.mode
        insn = int.from_bytes(image[pc - BASE:pc - BASE + 4], 'little')
        before = len(taken)
        hart.step()
        trap = len(taken) > before
        record = {k: '0x0' for k in 'rs1_rdata rs2_rdata rd_wdata mem_addr mem_rdata mem_wdata'.split()}
        record.update(order=order, cycle=order, pc=hex(pc), pc_next=hex(hart.pc), insn=hex(insn), mode=mode, trap=trap,
                      intr=previous_trap, halt=False, rs1=0, rs2=0, rd=0, mem_rmask=0, mem_wmask=0, mem_fault=False)
        records.append(record)
        if trap:
            records.append(dict(event='trap', cycle=order, cause=hex(taken[-1][0]), tval=hex(taken[-1][1]), intr=False))
        previous_trap = trap
        order += 1
        if pc == done:
            break
    records.append(dict(event='end', cycle=order, status='pass'))
    path.write_text(''.join(json.dumps(r) + '\n' for r in records))
    return [(BASE, image)]


@pytest.fixture
def flow(tmp_path):
    rvfi = tmp_path / 'c2.jsonl'
    code = run_c2(rvfi)
    return rvfi, code, tmp_path


def test_pack_unpack_round_trip():
    p = ntrace.normalize({'src_bits': 3})
    messages = [ntrace.Message('ProgTraceSync', {'sync': 1, 'icnt': 0, 'faddr': 0x40000000}, src=5),
                ntrace.Message('IndirectBranchHist', {'btype': 1, 'icnt': 300, 'uaddr': 0x7, 'hist': 0b1011}),
                ntrace.Message('Error', {'etype': 0, 'ecode': 0}),
                ntrace.Message('ProgTraceCorrelation', {'evcode': 4, 'cdf': 1, 'icnt': 0, 'hist': 1})]
    data = ntrace.pack(messages, p)
    assert all(b & 3 in (0, 1, 3) for b in data) and data[-1] & 3 == 3
    back, rest = ntrace.unpack(data, p)
    assert [m.as_dict() for m in back] == [m.as_dict() for m in messages] and rest == 0
    back, rest = ntrace.unpack(data[:-1], p)
    assert rest > 0
    with pytest.raises(ValueError):
        ntrace.unpack(bytes([63 << 2 | 3]), p)


def test_direct_targets():
    assert ntrace.direct_target(Asm.jal(0, -16), 0x100) == 0xf0
    assert ntrace.direct_target(Asm.bne(1, 0, 24), 0x100) == 0x118
    assert ntrace.direct_target(0xa001, 0x100) == 0x100      # c.j .
    assert ntrace.direct_target(Asm.NOP, 0x100) is None


@pytest.mark.parametrize('mode', ['htm', 'btm'])
@pytest.mark.parametrize('period', [0, 2])
def test_reference_stream_matches_c2(flow, mode, period):
    rvfi, code, tmp = flow
    profile = {'mode': mode, 'sync_period': period}
    result, data = nc.check(rvfi, code, profile=profile)
    assert result['status'] == 'no_checks'
    capture = tmp / 'capture.bin'
    capture.write_bytes(data)
    result, _ = nc.check(rvfi, code, profile=profile, packets=capture)
    assert result['status'] == 'flow_match' and result['messages']['status'] == 'message_match', result
    assert result['qualified'] == result['retired'] > 20


def test_corruption_truncation_and_leak(flow):
    rvfi, code, tmp = flow
    profile = {'mode': 'htm', 'sync_period': 2}
    _, data = nc.check(rvfi, code, profile=profile)
    messages, _ = ntrace.unpack(data, ntrace.normalize(profile))
    bad = [ntrace.Message(m.name, dict(m.fields), m.src) for m in messages]
    index = next(i for i, m in enumerate(bad) if m.name == 'IndirectBranchHist' and m.fields['icnt'] > 4)
    bad[index].fields['icnt'] += 2
    (tmp / 'bad.bin').write_bytes(ntrace.pack(bad, ntrace.normalize(profile)))
    result, _ = nc.check(rvfi, code, profile=profile, packets=tmp / 'bad.bin')
    assert result['status'] == 'mismatch'
    (tmp / 'cut.bin').write_bytes(data[:-2])
    result, _ = nc.check(rvfi, code, profile=profile, packets=tmp / 'cut.bin')
    assert result['status'] != 'flow_match'
    machine = {'privileges': [3]}
    (tmp / 'all.bin').write_bytes(data)
    result, _ = nc.check(rvfi, code, profile=profile, packets=tmp / 'all.bin', filter_spec=machine)
    assert result['status'] == 'leak' and result['leaked_pcs']
    _, filtered = nc.check(rvfi, code, profile=profile, filter_spec=machine)
    (tmp / 'filtered.bin').write_bytes(filtered)
    result, _ = nc.check(rvfi, code, profile=profile, packets=tmp / 'filtered.bin', filter_spec=machine)
    assert result['status'] == 'flow_match' and result['qualified'] < result['retired']


@pytest.mark.parametrize('mode', ['htm', 'btm'])
def test_loss_campaign(flow, mode):
    rvfi, code, tmp = flow
    tests = nc.loss_campaign(rvfi, code, profile={'mode': mode, 'sync_period': 2})
    assert len(tests) >= 8 and {t['status'] for t in tests} == {'pass'}, [t for t in tests if t['status'] != 'pass']
    assert any(t['unknown_instructions'] for t in tests)


def test_loss_without_marker_is_not_a_match(flow):
    rvfi, code, tmp = flow
    profile = {'mode': 'htm', 'sync_period': 2}
    _, data = nc.check(rvfi, code, profile=profile)
    p = ntrace.normalize(profile)
    messages, _ = ntrace.unpack(data, p)
    index = next(i for i, m in enumerate(messages) if m.name == 'IndirectBranchHist')
    silent = messages[:index] + messages[index + 1:]
    (tmp / 'silent.bin').write_bytes(ntrace.pack(silent, p))
    result, _ = nc.check(rvfi, code, profile=profile, packets=tmp / 'silent.bin')
    assert result['status'] == 'mismatch'
    result, _ = nc.check(rvfi, code, profile=profile, packets=tmp / 'silent.bin', losses=[index])
    assert result['status'] == 'partial_match'


def test_adapter_template_verifies_and_vendor_name_alone_fails(tmp_path):
    template = ROOT / 'examples/trace/nexus-htm-template.toml'
    adapter = nc.load_adapter(template)
    assert adapter['verified'] and len(adapter['vectors']) == 4
    named = tmp_path / 'vendor.toml'
    named.write_text('schema = "rvw.trace-adapter/1"\nname = "sifive"\nvendor = "SiFive"\ncodec = "rvw-ntrace/1"\n'
                     'specification = "x"\nlicense = "x"\n')
    with pytest.raises(nc.AdapterError, match='vectors'):
        nc.load_adapter(named)
    wrong = tmp_path / 'wrong.toml'
    wrong.write_text(template.read_text().replace('bytes = "70 71 b1 17"', 'bytes = "70 71 b1 13"'))
    adapter = nc.load_adapter(wrong)
    assert not adapter['verified']
    with pytest.raises(nc.AdapterError, match='failed'):
        nc.params_for(adapter=adapter)


def test_api_writes_results(flow):
    rvfi, code, tmp = flow
    words, _ = program()
    summary = api.ntrace_loss(tmp / 'loss', rvfi, code, sync_period=2)
    assert summary['status'] == 'pass'
    results = json.loads((tmp / 'loss/results.json').read_text())
    from rvw.results.schema import validate_results
    assert not validate_results(results) and results['suite'] == 'ntrace-loss'
