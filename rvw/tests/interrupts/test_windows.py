import json
from window_check import check_interrupts


def test_missing_and_mismatched_inputs(tmp_path):
    p = tmp_path / 'trace.jsonl'
    header = dict(schema='rvw.rvfi/1', xlen=64, isa='rv64i', core='fixture', config='test', elf='test')
    rows = [header, dict(event='irq', cycle=1, levels='0x0'), dict(event='end', cycle=100, status='pass')]
    p.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    assert check_interrupts(p, [])['status'] == 'inconclusive'
    assert check_interrupts(p, [(1, 8)])['status'] == 'mismatch'
    assert check_interrupts(p, [(1, 0)])['status'] == 'inconclusive'
    assert check_interrupts(p, [(1, 0)], cause=1 << 63 | 7)['status'] == 'inconclusive'


def test_independent_bounds_reject_wrong_time_cause_and_state(tmp_path):
    from rvw.cosim.trace import record
    p = tmp_path / 'trace.jsonl'
    header = dict(schema='rvw.rvfi/1', xlen=64, isa='rv64i', core='fixture', config='test', elf='test')
    cause = (1 << 63) | 7
    def instruction(order, pc, rd, value):
        e = dict(pc=pc, pc_next=pc+4, insn=0x13, mode=3, rd=rd, rd_wdata=value,
                 mem_addr=0, mem_rmask=0, mem_wmask=0, mem_rdata=0, mem_wdata=0,
                 trap=False, mem_fault=False, before=[0]*32)
        return record(e, order, cycle=10+order)
    rows = [header, dict(event='irq', cycle=1, levels='0x80'),
            instruction(0, 0x100, 0, 0),
            dict(event='trap', cycle=10, cause=hex(cause), tval='0x0', intr=True),
            instruction(1, 0x200, 9, cause), instruction(2, 0x204, 18, 0x100),
            instruction(3, 0x208, 19, 0x80), dict(event='end', cycle=20, status='pass')]
    def check(schedule=((1, 128),), **changes):
        p.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        kwargs = dict(cause=cause, window=(2, 15), handler_pc=0x200, mode=3, epc_range=(0x100, 0x108))
        return check_interrupts(p, schedule, **(kwargs | changes))['status']
    assert check() == 'consistent'
    assert check(schedule=[(1, 128), (5, 128)]) == 'consistent'
    assert check(window=(11, 20)) == 'mismatch'
    assert check(cause=cause ^ 4) == 'mismatch'
    assert check(window=None) == 'inconclusive'
    rows[-2]['rd_wdata'] = '0x88'
    assert check() == 'mismatch'
