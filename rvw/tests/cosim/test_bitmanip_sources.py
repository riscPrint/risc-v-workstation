"""Zba/Zbb/Zbs operand evidence and refusal of unknown successful instructions."""
import pytest

from rvw.common.riscv import decode
from rvw.cosim.trace import record


# Match words from Spike encoding.h and the GNU assembler. Set rs1=a0, rs2=a1,
# rd=a2 below. Immediate encodings keep their fixed selector or shift amount.
BINARY = [
    (0x20002033, 'sh1add', 32), (0x20004033, 'sh2add', 32), (0x20006033, 'sh3add', 32),
    (0x0800003b, 'add.uw', 64), (0x2000203b, 'sh1add.uw', 64),
    (0x2000403b, 'sh2add.uw', 64), (0x2000603b, 'sh3add.uw', 64),
    (0x40007033, 'andn', 32), (0x40006033, 'orn', 32), (0x40004033, 'xnor', 32),
    (0x0a004033, 'min', 32), (0x0a005033, 'minu', 32),
    (0x0a006033, 'max', 32), (0x0a007033, 'maxu', 32),
    (0x60001033, 'rol', 32), (0x60005033, 'ror', 32),
    (0x6000103b, 'rolw', 64), (0x6000503b, 'rorw', 64),
    (0x48001033, 'bclr', 32), (0x48005033, 'bext', 32),
    (0x68001033, 'binv', 32), (0x28001033, 'bset', 32),
]
UNARY = [
    (0x60001013, 'clz', 32), (0x60101013, 'ctz', 32), (0x60201013, 'cpop', 32),
    (0x6000101b, 'clzw', 64), (0x6010101b, 'ctzw', 64), (0x6020101b, 'cpopw', 64),
    (0x60401013, 'sext.b', 32), (0x60501013, 'sext.h', 32), (0x28705013, 'orc.b', 32),
    (0x60005013, 'rori', 32), (0x6000501b, 'roriw', 64), (0x0800101b, 'slli.uw', 64),
    (0x48001013, 'bclri', 32), (0x48005013, 'bexti', 32),
    (0x68001013, 'binvi', 32), (0x28001013, 'bseti', 32),
]


def effect(word):
    return dict(insn=word, before=[0, *range(101, 132)], mode=3, rd=12,
                mem_rmask=0, mem_wmask=0, trap=False, mem_fault=False)


@pytest.mark.parametrize('base,name,minimum', BINARY + UNARY)
@pytest.mark.parametrize('xlen', [32, 64])
def test_bitmanip_sources(base, name, minimum, xlen):
    binary = (base, name, minimum) in BINARY
    word = base | 10 << 15 | 12 << 7 | (11 << 20 if binary else 0)
    if xlen < minimum:
        assert decode(word, xlen).mnemonic == 'unknown'
        return
    assert decode(word, xlen).mnemonic == name
    row = record(effect(word), 0, xlen=xlen)
    assert (row['rs1'], row['rs2']) == (10, 11 if binary else 0)
    assert (row['rs1_rdata'], row['rs2_rdata']) == ('0x6e', '0x6f' if binary else '0x0')


@pytest.mark.parametrize('xlen,rev8,zext_h', [(32, 0x69805013, 0x08004033),
                                           (64, 0x6b805013, 0x0800403b)])
def test_xlen_specific_unary_encodings(xlen, rev8, zext_h):
    for base, name in ((rev8, 'rev8'), (zext_h, 'zext.h')):
        word = base | 10 << 15 | 12 << 7
        assert decode(word, xlen).mnemonic == name
        assert decode(word, 96 - xlen).mnemonic == 'unknown'
        row = record(effect(word), 0, xlen=xlen)
        assert (row['rs1'], row['rs2'], row['rs1_rdata'], row['rs2_rdata']) == (10, 0, '0x6e', '0x0')


@pytest.mark.parametrize('base', [0x60005013, 0x48001013, 0x48005013, 0x68001013, 0x28001013])
def test_bitmanip_immediate_width(base):
    for amount in range(64):
        word = base | amount << 20 | 10 << 15 | 12 << 7
        assert decode(word, 64).mnemonic != 'unknown'
        assert (decode(word, 32).mnemonic == 'unknown') == (amount >= 32)
        assert record(effect(word), 0)['rs2'] == 0


def test_unknown_successful_instruction_cannot_generate_zero_sources():
    with pytest.raises(ValueError, match='source.*unknown|unknown.*source'):
        record(effect(0x0000000b), 0)  # A custom opcode can execute in an extended reference.


def test_unknown_trapping_instruction_can_still_be_recorded():
    e = effect(0)
    e['trap'] = True
    assert record(e, 0)['trap'] is True


@pytest.mark.parametrize('word,xlen', [
    (0x60001033 | 2 << 12, 64),  # Reserved rotate funct3.
    (0x6040101b, 64),            # No sext.b word form.
    (0x6050101b, 64),            # No sext.h word form.
    (0x0800403b | 1 << 20, 64),  # zext.h requires rs2=0.
    (0x0a00403b, 64),            # No min word form.
    (0x2800103b, 64),            # No bset word form.
    (0x2000203b, 32),            # sh1add.uw requires RV64.
    (0x6200501b, 64),            # roriw requires a 5-bit shift amount.
])
def test_reserved_bitmanip_encodings_stay_unknown(word, xlen):
    assert decode(word, xlen).mnemonic == 'unknown'


@pytest.mark.parametrize('xlen', [32, 64])
def test_native_bitmanip_trace_operands(tmp_path, tmp_path_factory, platform, xlen):
    from dataclasses import replace
    import json
    from pathlib import Path
    from cosim_build import _build
    from model_fixtures import generate

    operations = [(name, True) for _, name, minimum in BINARY if xlen >= minimum]
    operations += [(name, False) for _, name, minimum in UNARY if xlen >= minimum]
    operations += [('rev8', False), ('zext.h', False)]
    assembly = []
    for name, binary in operations:
        operand = ', a1' if binary else ', 0' if name.endswith('i') or name in ('roriw', 'slli.uw') else ''
        assembly.append(f'  {name} a2, a0{operand}')
    source = tmp_path / 'bitmanip.S'
    text = Path(__file__).with_name('program_mul.S').read_text()
    text = text.replace('  mul a2, a0, a1', '\n'.join(assembly))
    if xlen == 32:
        text = text.replace('sd t1', 'sw t1')
    source.write_text(text)
    isa = f'rv{xlen}ima_zicsr_zba_zbb_zbs'
    elf = _build(tmp_path_factory, source, march=isa, mabi='lp64' if xlen == 64 else 'ilp32')
    trace = tmp_path / 'trace.jsonl'
    result = generate(elf, trace, replace(platform, xlen=xlen, isa=isa, reference_isa=None, csr_masks={}), 100)
    assert result['termination'] == 'pass'
    rows = [json.loads(line) for line in trace.read_text().splitlines()]
    rows = [row for row in rows if 'insn' in row and row['rd'] == 12]
    assert len(rows) == len(operations)
    for row, (name, binary) in zip(rows, operations):
        assert decode(int(row['insn'], 16), xlen).mnemonic == name
        assert (row['rs1'], row['rs2']) == (10, 11 if binary else 0)
        assert (row['rs1_rdata'], row['rs2_rdata']) == ('0x6', '0x7' if binary else '0x0')
        assert row['trap'] is False
