import json
import pytest

from rvw.cov.functional import decode, functional, observations


def trace(path, rows):
    header = {"schema": "rvw.rvfi/1", "xlen": 64, "isa": "rv64imc"}
    path.write_text('\n'.join(json.dumps(r) for r in [header, *rows]) + '\n')
    return path


def row(order, insn, **extra):
    return {"order": order, "insn": hex(insn), "mode": 3, "rd": 1,
            "rs1_rdata": "0x0", "rs2_rdata": "0x0", **extra}


def bins(result, group):
    return {tuple(h['bin']): h['count'] for h in result['groups'][group]['hits']}


def test_classes_dependencies_csr_traps_and_holes(tmp_path):
    path = trace(tmp_path / 'trace.jsonl', [row(0, 0x00100093), row(1, 0x00108133, rd=2),
        row(2, 0x00000063, rd=0), row(3, 0x300020f3),
        row(4, 0x00003083, mem_addr='0x3', mem_rmask=255),
        {"event": "trap", "cause": "0x2", "intr": False}])
    result = functional([path])
    assert bins(result, 'dependency')[(True, 'alu')] == 1
    assert bins(result, 'branch')[(True, 'M')] == 1
    assert bins(result, 'memory')[('read', 8, 'misaligned')] == 1
    assert bins(result, 'csr')[('0x300', 'read', 'M')] == 1
    assert bins(result, 'trap_cause_mode')[(2, 'unknown')] == 1
    assert ['branch', 'U'] in result['groups']['class_mode']['holes']
    assert result['retired'] == 5


def test_custom_bins_merge_and_duplicate_rejection(tmp_path):
    config = tmp_path / 'plan.json'
    config.write_text(json.dumps({"groups": [{"name": "pc", "fields": ["pc"],
        "when": {"mode": {"in": ["M"]}}, "bins": [["0x100"], ["0x104"]]}]}))
    a = trace(tmp_path / 'a.jsonl', [row(0, 0x13, pc='0x100')])
    b = trace(tmp_path / 'b.jsonl', [row(0, 0x13, pc='0x104')])
    first = functional([a], config)
    saved = tmp_path / 'saved.json'
    saved.write_text(json.dumps(first, indent=2))
    merged = functional([saved, b], config)
    assert merged['groups']['pc']['holes'] == []
    assert 'class_mode' in merged['groups']
    assert merged['retired'] == 2
    with pytest.raises(ValueError, match='duplicate trace'):
        functional([saved, a], config)


def test_noncontiguous_mask_and_immediate_no_false_dependency():
    obs, _ = observations(row(0, 0x00100093, rd=1, mem_addr='0x0', mem_rmask=5), 64, ('x', 1))
    assert obs[0]['back_to_back'] is False
    assert obs[1]['alignment'] == 'noncontiguous-mask'
    assert decode(0x02004033)['mnemonic'] == 'div'
    assert decode(0x9002)['mnemonic'] == 'c.ebreak'
    assert decode(0x40a2)['mnemonic'] == 'c.lwsp'
    assert decode(0xa001)['class'] == 'jump'


def test_branch_outcome_from_operands_not_pc_and_x0():
    obs, dest = observations(row(0, 0x00000063, rd=0, pc='0x100', pc_next='0x104'), 64, None)
    assert obs[0]['branch_taken'] is True
    assert dest is None


def test_floating_store_register_bank_dependency():
    # FSW f1,0(x0): the address uses x0 and the data consumes f1.
    obs, dest = observations(row(0, (1 << 20) | (2 << 12) | 0x27, rd=0), 64, ('f', 1))
    assert obs[0]['back_to_back'] is True
    assert dest is None


def test_handler_entry_does_not_imply_asynchronous_interrupt(tmp_path):
    path = trace(tmp_path / 'trap.jsonl', [row(0, 0x13, intr=True),
        {"event": "trap", "cause": "0xb", "intr": False, "mode": 3}])
    result = functional([path])
    assert bins(result, 'handler_entry') == {('M',): 1}
    assert bins(result, 'interrupt_cause_mode') == {}
    assert bins(result, 'trap_cause_mode') == {(11, 'M'): 1}


def test_interrupt_cause_high_bit_and_mode(tmp_path):
    path = trace(tmp_path / 'interrupt.jsonl', [
        {"event": "trap", "cause": "0x800000000000000b", "intr": True, "mode": 1}])
    result = functional([path])
    assert bins(result, 'interrupt_cause_mode') == {(11, 'S'): 1}
    assert bins(result, 'trap_cause_mode') == {}


def test_irq_level_events_keep_the_dependency_pair(tmp_path):
    # x1 = 1; [irq input-level event]; x2 = x1 + x1 -> still a back-to-back dependency
    rows = [row(0, 0x00100093), {"event": "irq", "cycle": 5, "mip": "0x80"}, row(1, 0x00108133, rd=2)]
    result = functional([trace(tmp_path / 'irq.jsonl', rows)])
    assert bins(result, 'dependency')[(True, 'alu')] == 1


# Round 10: aligned-memory traces put the word address in mem_addr and the lane offset in the mask.
LH = 0x00009503   # lh a0, 0(ra)


def lh_trace(path, mem_addr, mask, core=None, xlen=64):
    header = {"schema": "rvw.rvfi/1", "xlen": xlen, "isa": f"rv{xlen}imc", **({"core": core} if core else {})}
    rows = [row(0, LH, rd=10, mem_addr=mem_addr, mem_rmask=mask)]
    path.write_text('\n'.join(json.dumps(r) for r in [header, *rows]) + '\n')
    return path


def test_alignment_uses_the_active_lane_offset():
    probe = {'order': 0, 'insn': hex(LH), 'mode': 3, 'rs1': 1, 'rs1_rdata': '0x80000001', 'rd': 10,
             'mem_addr': '0x80000000', 'mem_rmask': 6}   # lh at 0x80000001 in ALIGNED_MEM form
    assert observations(probe, 64, None, True)[0][1]['alignment'] == 'misaligned'
    assert observations({**probe, 'mem_rmask': 12}, 64, None, True)[0][1]['alignment'] == 'aligned'
    # Unknown or byte-address convention: a lane-shifted mask cannot be placed.
    assert observations(probe, 64, None, None)[0][1]['alignment'] == 'undetermined'
    assert observations(probe, 64, None, False)[0][1]['alignment'] == 'undetermined'
    # ALIGNED_MEM with a word address that is not aligned, or lanes past the word: malformed.
    assert observations({**probe, 'mem_addr': '0x80000002'}, 64, None, True)[0][1]['alignment'] == 'undetermined'
    assert observations({**probe, 'mem_rmask': 0x180}, 64, None, True)[0][1]['alignment'] == 'undetermined'
    # Byte-address convention: mem_addr is the access address.
    byte = {**probe, 'mem_addr': '0x80000001', 'mem_rmask': 3}
    assert observations(byte, 64, None, False)[0][1]['alignment'] == 'misaligned'
    assert observations(byte, 64, None, None)[0][1]['alignment'] == 'misaligned'


def test_alignment_convention_comes_from_the_platform(tmp_path):
    # BOOM's bundled platform declares aligned_mem: the header's core selects it.
    result = functional([lh_trace(tmp_path / 'boom.jsonl', '0x80000000', 6, core='boom')])
    assert bins(result, 'memory') == {('read', 2, 'misaligned'): 1}
    assert next(iter(result['traces'].values()))['address_convention'] == 'aligned_mem'
    # No platform for the core: undetermined, never counted as aligned.
    result = functional([lh_trace(tmp_path / 'other.jsonl', '0x80000000', 6, core='nosuchcore')])
    assert bins(result, 'memory') == {('read', 2, 'undetermined'): 1}
    assert ['read', 2, 'aligned'] in result['groups']['memory']['holes']
    # An explicit platform (name or JSON file) wins over the header.
    result = functional([lh_trace(tmp_path / 'x.jsonl', '0x80000000', 6, core='nosuchcore')], platform='boom')
    assert bins(result, 'memory') == {('read', 2, 'misaligned'): 1}
    with pytest.raises(ValueError):   # the platform's XLEN must match the trace
        functional([lh_trace(tmp_path / 'rv32.jsonl', '0x80000000', 6, core='boom', xlen=32)])


def test_fp_destination_comes_from_the_encoding_not_c2_rd():
    # Round 14 (/tmp/review14-c/probe_fp_dependencies.py): C2 `rd` is RVFI's integer write, 0 for an
    # FP write, and every FP result was taken as f0. BOOM's rv64ud-p-fadd: fadd.d f13,f10,f11 then
    # fmv.x.d a0,f13 is a dependency; a consumer of f0 is not.
    fadd, fmv_f13 = 0x02b576d3, 0xe2068553
    fmv_f0 = fmv_f13 & ~(31 << 15)
    _, dest = observations(row(0, fadd, rd=0), 64, None)
    assert dest == ('f', 13)
    obs, _ = observations(row(1, fmv_f13, rd=10), 64, dest)
    assert obs[0]['back_to_back'] is True
    obs, _ = observations(row(1, fmv_f0, rd=10), 64, dest)
    assert obs[0]['back_to_back'] is False
    # Compressed FP loads: c.fld rd' (bits 4:2) and c.fldsp rd (bits 11:7).
    assert observations(row(0, 0x2004 | (3 << 2), rd=0), 64, None)[1] == ('f', 11)  # c.fld f11, 0(s0)
    assert observations(row(0, 0x2002 | (7 << 7), rd=0), 64, None)[1] == ('f', 7)   # c.fldsp f7, 0(sp)
    # A trace that reports an integer write for an FP-destination instruction contradicts the
    # encoding: the next dependency is undetermined, not True or False.
    _, dest = observations(row(0, fadd, rd=5), 64, None)
    obs, after = observations(row(1, fmv_f13, rd=10), 64, dest)
    assert obs[0]['back_to_back'] == 'undetermined' and after == ('x', 10)
    obs, _ = observations(row(1, 0x00000537, rd=10), 64, dest)  # lui reads nothing: no dependency
    assert obs[0]['back_to_back'] is False


def test_fp_dependency_bins_in_a_trace(tmp_path):
    path = trace(tmp_path / 'fp.jsonl', [row(0, 0x02b576d3, rd=0), row(1, 0xe2068553, rd=10)])
    result = functional([path])
    assert bins(result, 'dependency') == {(False, 'float'): 1, (True, 'float'): 1}, bins(result, 'dependency')
