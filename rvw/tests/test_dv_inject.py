"""Seeded trap and CSR injection derives every choice from the target profile."""
import random
import pytest
from rvw.regress import dv_inject

pytestmark = pytest.mark.fast

PROGRAM = """.include "user_define.h"
_start:
                  .include "user_init.s"
init:
                  li x1, 0
main:             add x1, x2, x3
                  sub x4, x5, x6
                  xor x7, x8, x9
                  la x30, test_done
                  jalr x0, x30, 0
test_done:
"""
TARGET = dict(isa='rv32im_zicsr_zifencei', xlen=32, csrs=[
    dict(name='mscratch', address=0x340, assembly_safe=True),
    dict(name='sscratch', address=0x140, present=False, assembly_safe=True),
    dict(name='mcycle', address=0xb00)])


def decode_ok(word, isa='rv32im', xlen=32):
    """Small independent RV32IM/RV64IM legality model for the generated words."""
    op, f3, f7 = word & 0x7f, (word >> 12) & 7, word >> 25
    legal = dv_inject.legal_opcodes(isa, xlen)
    if op not in legal:
        return False
    if op == 0x03:
        return f3 in ((0, 1, 2, 4, 5) if xlen == 32 else (0, 1, 2, 3, 4, 5, 6))
    if op == 0x23:
        return f3 in ((0, 1, 2) if xlen == 32 else (0, 1, 2, 3))
    if op == 0x63:
        return f3 not in (2, 3)
    if op == 0x67:
        return f3 == 0
    if op == 0x33:
        return f7 in (0, 0x20, 1) and (f7 != 0x20 or f3 in (0, 5)) and (f7 != 1 or 'm' in isa[4:])
    if op == 0x13 and f3 == 1:
        return (word >> (26 if xlen == 64 else 25)) == 0
    if op == 0x13 and f3 == 5:
        top = word >> (26 if xlen == 64 else 25)
        return top in (0, 0x10 if xlen == 64 else 0x20)
    return True


@pytest.mark.parametrize('isa,xlen', [('rv32im_zicsr', 32), ('rv64im_zicsr', 64), ('rv32ima', 32)])
def test_illegal_words_are_undefined_for_the_declared_isa(isa, xlen):
    rng = random.Random(1)
    kinds = set()
    for _ in range(2000):
        word, kind = dv_inject.illegal_words(isa, xlen, rng)
        kinds.add(kind)
        assert word & 3 == 3 or word == 0
        assert not decode_ok(word, isa.split('_')[0], xlen), (hex(word), kind)
    assert {'opcode', 'zero', 'op_funct7', 'shift_funct7'} <= kinds


def test_declared_extension_opcodes_are_never_illegal():
    rng = random.Random(2)
    words = [dv_inject.illegal_words('rv32ima', 32, rng)[0] for _ in range(2000)]
    assert all(w & 0x7f != 0x2f for w in words)
    # An unknown Z extension may reuse OP funct7 space: skip funct7 kinds.
    kinds = {dv_inject.illegal_words('rv32im_zbb', 32, rng)[1] for _ in range(500)}
    assert not kinds & {'op_funct7', 'shift_funct7'}


def test_trap_injection_stays_in_main_and_marks_the_handler():
    text, records = dv_inject.inject(PROGRAM, TARGET, 'traps', 5, 4)
    assert text.startswith(dv_inject.TRAP_MARK)
    lines = text.splitlines()
    main = next(i for i, l in enumerate(lines) if l.startswith('main:'))
    done = next(i for i, l in enumerate(lines) if 'la x30, test_done' in l)
    inserted = [i for i, l in enumerate(lines) if 'rvw illegal' in l]
    assert len(inserted) == len(records) == 4 and all(main < i < done for i in inserted)
    assert (text, records) == dv_inject.inject(PROGRAM, TARGET, 'traps', 5, 4)


def test_csr_injection_uses_only_present_assembly_safe_csrs():
    text, records = dv_inject.inject(PROGRAM, TARGET, 'csr', 3, 20)
    assert {r['csr'] for r in records} == {'mscratch'}
    assert ' 0x340, ' in text and '0x140' not in text and '0xb00' not in text
    assert dv_inject.TRAP_MARK not in text


def test_csr_class_refuses_a_selection_without_safe_csrs():
    with pytest.raises(ValueError, match='assembly-safe'):
        dv_inject.inject(PROGRAM, dict(TARGET, csrs=[]), 'csr', 1, 1)


def test_program_without_main_region_is_refused():
    with pytest.raises(ValueError, match='main region'):
        dv_inject.inject('nop\n', TARGET, 'traps', 1, 1)
