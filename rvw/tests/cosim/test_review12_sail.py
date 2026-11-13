"""Round 12 (cosim): Sail decodes RV32 compressed FP load/store offsets with RV32 layouts."""
import copy
import json

import pytest

from rvw.cosim.checker import check
from model_fixtures import generate
from model_fixtures import Sail
from rvw.cosim.sail import memory_operand


# --- Sail: compressed FP loads/stores on RV32 use word layouts -------------------------------------

@pytest.mark.parametrize("insn,operand", [
    (0x6148, (10, 4)),    # c.flw fa0, 4(a0)
    (0xE548, (10, 12)),   # c.fsw fa0, 12(a0)
    (0x6592, (2, 4)),     # c.flwsp fa1, 4(sp)
    (0xEA2E, (2, 20)),    # c.fswsp fa1, 20(sp)
    (0x2510, (10, 8)),    # c.fld fa2, 8(a0)
    (0xA910, (10, 16)),   # c.fsd fa2, 16(a0)
    (0x4050, (8, 4)),     # c.lw a2, 4(s0)
    (0x4732, (2, 12)),    # c.lwsp a4, 12(sp)
])
def test_rv32_compressed_operands(insn, operand):
    assert memory_operand(insn, 32) == operand


@pytest.mark.parametrize("insn,operand", [
    (0x640C, (8, 8)),     # c.ld a1, 8(s0)
    (0xE80C, (8, 16)),    # c.sd a1, 16(s0)
    (0x66A2, (2, 8)),     # c.ldsp a3, 8(sp)
    (0xF436, (2, 40)),    # c.sdsp a3, 40(sp)
    (0x2510, (10, 8)),    # c.fld fa2, 8(a0)
    (0xA910, (10, 16)),   # c.fsd fa2, 16(a0)
])
def test_rv64_compressed_operands(insn, operand):
    assert memory_operand(insn, 64) == operand


def test_memory_operand_needs_xlen():
    with pytest.raises(TypeError):
        memory_operand(0x6148)


def rv32(platform):
    p = copy.copy(platform)
    p.xlen = 32
    p.isa = "rv32imafdc_zicsr_zifencei"
    p.reference_isa = p.isa + "_zicntr_zihpm"
    p.csr_masks = {}
    p.mode_after_change = False
    p.illegal_insn_tval = "insn"
    p.sail_overrides = {"extensions": {"Sv39": {"supported": False}, "Sv32": {"supported": True}}}
    return p


def test_sail_checks_native_rv32_compressed_fp_address_scope(tmp_path, rv32_cfp_elf, platform, sail):
    """Check native RV32 compressed FP addresses. Refuse full FP-state comparison."""
    p = rv32(platform)
    trace = tmp_path / "rv32.jsonl"
    generated = generate(rv32_cfp_elf, trace, p, 100)
    assert generated["status"] == "generated" and generated["termination"] == "pass"
    original = trace.read_bytes()
    full_rows = [json.loads(line) for line in original.splitlines()]
    assert full_rows[0]['schema'] == 'rvw.rvfi/2'
    assert any(row.get('fd_valid') for row in full_rows[1:])
    model = Sail(p, rv32_cfp_elf, trace, sail, timeout=60)
    try:
        # Sail has no FP-state observations. Keep the full-state refusal.
        with pytest.raises(ValueError, match='reference cannot check C2 state fields'):
            check(trace, model, p)
    finally:
        model.close()
    # This test checks address decoding. Retain the full trace and make a
    # separate C2/1 projection with an explicit no-FP-state comparison scope.
    rows = copy.deepcopy(full_rows)
    rows[0]['schema'] = 'rvw.rvfi/1'
    rows[0].pop('capabilities')
    rows[0]['config'] = 'address-scope-no-fp-state'
    for row in rows[1:]:
        for key in ('fd_valid', 'fd', 'fd_wdata', 'fflags', 'fcsr'):
            row.pop(key, None)
    scoped = tmp_path / 'address-scope.jsonl'
    scoped.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    model = Sail(p, rv32_cfp_elf, scoped, sail, timeout=60)
    try:
        result = check(scoped, model, p)
    finally:
        model.close()
    assert result['scope'] == 'no_fp_state'
    assert result['state_coverage']['fp'] is False
    assert trace.read_bytes() == original
    # An address error must still fail the scoped comparison.
    bad_rows = copy.deepcopy(rows)
    load = next(row for row in bad_rows[1:] if row.get('mem_rmask'))
    load['mem_addr'] = hex(int(load['mem_addr'], 16) + 4)
    bad = tmp_path / 'bad-address.jsonl'
    bad.write_text(''.join(json.dumps(row)+'\n' for row in bad_rows))
    model = Sail(p, rv32_cfp_elf, bad, sail, timeout=60)
    try:
        rejected = check(bad, model, p)
    finally:
        model.close()
    assert rejected['status'] == 'mismatch'
    assert 'mem_addr' in rejected['mismatch']['differences']
    assert result["status"] == "match", result
    assert result["trace_complete"] and result["instructions"] >= 10
    accesses = [json.loads(x) for x in trace.read_text().splitlines()]
    assert sum(1 for r in accesses if r.get("mem_rmask") or r.get("mem_wmask")) >= 5
