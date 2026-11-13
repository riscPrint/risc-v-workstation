"""Operand-dependent latency rules on the OoO model, from a synthetic Spike-style C2 trace."""
import json
import pytest
from rvw.sec import model_check

pytestmark = pytest.mark.fast

DESCRIPTION = {"fetch_width": 1, "fetch_entries": 2, "rename_width": 1, "rob_entries": 4, "issue_width": 1,
               "issue_entries": 2, "load_entries": 1, "store_entries": 1, "commit_width": 1,
               "issue_order": "in_order", "latencies": {"alu": 1, "multiply": 3, "divide": 34, "load": 2, "store": 1}}


def trace(tmp_path, a, b):
    head = dict(schema='rvw.rvfi/1', xlen=32, isa='rv32im', core='t', config='t', elf='x')
    def row(i, insn, rd, rs1, rs2, ra, rb):
        return dict(pc=hex(0x80000000+4*i), pc_next=hex(0x80000004+4*i), insn=hex(insn), rd_wdata='0x0',
                    mem_addr='0x0', mem_rdata='0x0', mem_wdata='0x0', rs1=rs1, rs2=rs2, rs1_rdata=hex(ra),
                    rs2_rdata=hex(rb), order=i, cycle=i, mode=3, rd=rd, mem_rmask=0, mem_wmask=0, trap=False,
                    intr=False, halt=False, mem_fault=False)
    rows = [row(0, 0x027355b3, 11, 6, 7, a, b),   # divu x11, x6, x7
            row(1, 0x027305b3, 11, 6, 7, a, b),   # mul x11, x6, x7
            row(2, 0x00b50533, 10, 10, 11, 0, 0)]  # add x10, x10, x11
    path = tmp_path/f'{a}-{b}.jsonl'
    path.write_text('\n'.join(json.dumps(x) for x in [head, *rows, dict(event='end', cycle=3, status='pass')])+'\n')
    return path


def test_rules():
    row = dict(rs1_rdata=2**31-1, rs2_rdata=1)
    assert model_check.latency({'rule': 'quotient_bits', 'base': 4}, row, 'divu') == 35
    assert model_check.latency({'rule': 'quotient_bits', 'base': 4}, dict(rs1_rdata=7, rs2_rdata=3), 'divu') == 6
    assert model_check.latency({'rule': 'quotient_bits', 'base': 4}, dict(rs1_rdata=0xfffffff9, rs2_rdata=3), 'div') == 6
    assert model_check.latency({'rule': 'quotient_bits', 'base': 4}, dict(rs1_rdata=5, rs2_rdata=0), 'divu') == 5
    assert model_check.latency({'rule': 'early_out', 'width': 16, 'short': 1, 'long': 4}, row, 'mul') == 1
    assert model_check.latency({'rule': 'fixed', 'latency': 9}, row, 'divu') == 9
    with pytest.raises(ValueError, match='unknown latency rule'):
        model_check.latency({'rule': 'magic'}, row, 'divu')


def test_prediction_differs_only_with_a_dependent_rule(tmp_path):
    def cycles(rules, a, b):
        ops, rows, needed = model_check.trace_ops(trace(tmp_path, a, b), rules)
        assert ops[0].kind in ('divide', 'custom_divide_6', 'custom_divide_35', 'custom_divide_34')
        return model_check.predict(DESCRIPTION, ops, needed, 10000)[0]
    dependent = {'divide': {'rule': 'quotient_bits', 'base': 4}}
    assert cycles(dependent, 7, 3) < cycles(dependent, 2**31-1, 1)
    fixed = {'divide': {'rule': 'fixed', 'latency': 34}}
    assert cycles(fixed, 7, 3) == cycles(fixed, 2**31-1, 1)
    assert cycles({}, 7, 3) == cycles({}, 2**31-1, 1)
