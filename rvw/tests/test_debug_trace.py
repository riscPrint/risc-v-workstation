"""E-Trace flow helpers: trap ingress, windows, loss injection and filters (no native tools)."""
import json

import pytest

from rvw.debug import etrace_flow as ef

ADDI, BEQ, JALR, MRET, ECALL = 0x00000013, 0x00000063, 0x00008067, 0x30200073, 0x00000073


def c2(path, rows, events=(), end=True):
    records = [dict(schema='rvw.rvfi/1', xlen=64, isa='rv64i', core='t', config='t', elf='t')]
    for index, row in enumerate(rows):
        record = {k: '0x0' for k in 'rs1_rdata rs2_rdata rd_wdata mem_addr mem_rdata mem_wdata'.split()}
        record.update(order=index, cycle=index, pc=hex(row[0]), pc_next=hex(row[1]), insn=hex(row[2]),
                      mode=row[3] if len(row) > 3 else 3, trap=len(row) > 4 and row[4], intr=len(row) > 5 and row[5],
                      halt=False, rs1=0, rs2=0, rd=0, mem_rmask=0, mem_wmask=0, mem_fault=False)
        records.append(record)
        for at, event in events:
            if at == index:
                records.append(event)
    if end:
        records.append(dict(event='end', cycle=len(rows), status='pass'))
    path.write_text(''.join(json.dumps(r) + '\n' for r in records))
    return path


def test_retirement_attaches_trap_causes(tmp_path):
    rows = [(0x1000, 0x1004, ADDI), (0x1004, 0x2000, ECALL, 3, True), (0x2000, 0x2004, ADDI, 3, False, True),
            (0x2004, 0x3000, ADDI), (0x3000, 0x3004, ADDI, 3, False, True)]
    events = [(1, dict(event='trap', cycle=1, cause='0xb', tval='0x0', intr=False)),
              (3, dict(event='trap', cycle=3, cause=hex((1 << 63) | 7), tval='0x0', intr=True))]
    result, complete, xlen = ef.retirement(c2(tmp_path / 't.jsonl', rows, events))
    assert complete and xlen == 64
    assert result[1]['exc'] == (11, 0) and result[4]['irq'] == 7
    entries = ef.ingress_rows(result)
    kinds = [(e['itype_0'], e['iretire_0'], e['iaddr_0']) for e in entries]
    assert kinds == [(0, 1, '1000'), (1, 0, '1004'), (0, 1, '2000'), (0, 1, '2004'), (2, 0, '3000'), (0, 1, '3000')]
    assert entries[1]['cause'] == 11 and entries[4]['cause'] == 7
    assert ef.expected_pcs(result) == [0x1000, 0x2000, 0x2004, 0x3000]


def test_retirement_requires_trap_cause(tmp_path):
    with pytest.raises(ValueError, match='no trap event'):
        ef.retirement(c2(tmp_path / 't.jsonl', [(0x1000, 0x2000, ECALL, 3, True)]))


def test_ingress_kinds():
    rows = [dict(pc=0x1000, pc_next=0x1008, insn=BEQ | (8 << 7), mode=3),
            dict(pc=0x1008, pc_next=0x100c, insn=BEQ | (8 << 7), mode=3),
            dict(pc=0x100c, pc_next=0x4000, insn=JALR, mode=3),
            dict(pc=0x4000, pc_next=0x5000, insn=MRET, mode=3),
            dict(pc=0x5000, pc_next=0x5004, insn=ADDI, mode=0)]
    assert [e['itype_0'] for e in ef.ingress_rows(rows)] == [5, 4, 6, 6, 0]
    with pytest.raises(ValueError):
        ef.ingress_rows([dict(rows[0], mode=2)])
    with pytest.raises(ValueError):
        ef.ingress_rows([dict(rows[0], insn=0xffffffff)])
    with pytest.raises(ValueError):
        ef.ingress_rows([])


def sync(address):
    return {'format': '3', 'subformat': '0', 'address': f'{address:x}', 'qual_status': '_'}


SUPPORT_ON = {'format': '3', 'subformat': '3', 'ienable': '1', 'qual_status': '0', 'ioptions': '0', 'address': '_'}
SUPPORT_OFF = {'format': '3', 'subformat': '3', 'ienable': '0', 'qual_status': '1', 'ioptions': '0', 'address': '_'}
BRANCH = {'format': '1', 'subformat': '_', 'address': '4', 'qual_status': '_'}


def test_segments_resync_only_at_sync_start():
    stream = [SUPPORT_ON, sync(0x100), BRANCH, BRANCH, sync(0x200), BRANCH, SUPPORT_OFF]
    whole, skipped = ef.segments(stream)
    assert len(whole) == 1 and skipped == 0 and whole[0][0] == SUPPORT_ON
    cut, skipped = ef.segments(stream, losses=[3])
    assert len(cut) == 2 and skipped == 1            # BRANCH after the gap is skipped until sync
    assert cut[1][1] == sync(0x200)
    rows, ended = ef.close_segment(cut[0])
    assert not ended and rows[-1]['qual_status'] == '1' and rows[-1]['ienable'] == '0'
    lost = dict(SUPPORT_OFF, qual_status='2', ienable='1')
    segs, _ = ef.segments([SUPPORT_ON, sync(0x100), lost, BRANCH, sync(0x300), SUPPORT_OFF])
    assert len(segs) == 2
    rows, ended = ef.close_segment(segs[0])
    assert not ended and rows[-1]['qual_status'] == '1'


@pytest.mark.parametrize('kind,at,length,losses', [('drop', 2, 5, [2]), ('overflow', 2, 6, [3]),
                                                    ('wrap', 3, 3, [0]), ('truncate', 2, 3, [])])
def test_inject(kind, at, length, losses):
    stream = [SUPPORT_ON, sync(0x100), BRANCH, BRANCH, sync(0x200), SUPPORT_OFF]
    damaged, got = ef.inject(stream, kind, at)
    assert len(damaged) == length and got == losses
    with pytest.raises(ValueError):
        ef.inject(stream, 'bogus', 1)


def test_windows_and_verdicts():
    expected = list(range(10))
    report, observed = ef.windows([([0, 1, 2], True), ([6, 7, 8, 9], True)], expected)
    assert observed == 7 and [w['status'] for w in report] == ['observed', 'unknown', 'observed']
    assert ef.verdict(report, expected, complete=True, gaps=True) == 'partial_match'
    assert ef.verdict(report, expected, complete=True, gaps=False) == 'mismatch'
    assert ef.verdict(report, expected, complete=False, gaps=True) == 'inconclusive'
    full, _ = ef.windows([(expected, True)], expected)
    assert ef.verdict(full, expected, complete=True, gaps=False) == 'flow_match'
    late, _ = ef.windows([([3, 4], True)], expected)
    assert ef.verdict(late, expected, complete=True, gaps=True) == 'mismatch'   # no leading gap
    late, _ = ef.windows([([3, 4], True)], expected, leading_gap=True)
    assert ef.verdict(late, expected, complete=True, gaps=True) == 'partial_match'
    wrong, _ = ef.windows([([0, 1], True), ([5, 4], True)], expected)
    assert ef.verdict(wrong, expected, complete=True, gaps=True) == 'mismatch'


def test_filters_and_leaks():
    rows = [dict(pc=0x100 + 4 * i, mode=3 if i < 4 else 0) for i in range(8)]
    flags = ef.qualify(rows, {'privileges': [3]})
    assert flags == [True] * 4 + [False] * 4
    assert ef.qualify(rows, {'exclude': [[0x104, 0x108]]})[1] is False
    assert ef.qualify(rows, {'start': 0x108, 'stop': 0x110}) == [False, False, True, True, True, False, False, False]
    assert ef.qualify(rows, {'ranges': [[0x100, 0x108]]}) == [True, True] + [False] * 6
    assert [len(w) for w in ef.qualified_windows(rows, ef.qualify(rows, {'exclude': [[0x108, 0x10c]]}))] == [2, 5]
    assert ef.leaks([0x100, 0x104], rows, flags) == []
    assert ef.leaks([0x100, 0x110], rows, flags) == [0x110]
    assert ef.leaks([0x999], rows, flags) == [0x999]
    assert ef.packet_addresses([sync(0x110), BRANCH]) == [0x110]


def test_compare_packets():
    a = [SUPPORT_ON, sync(0x100), SUPPORT_OFF]
    assert ef.compare_packets(a, a)['status'] == 'packet_match'
    assert ef.compare_packets(a, [SUPPORT_ON, sync(0x104), SUPPORT_OFF])['field'] == 'address'
    assert ef.compare_packets(a[:2], a)['status'] == 'mismatch'
    assert ef.compare_packets([], [])['status'] == 'inconclusive'
