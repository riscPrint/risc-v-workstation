import pytest
from rvw.cov.fp import operand_class, report
pytestmark = pytest.mark.fast

@pytest.mark.parametrize('width,values', [(32, [0, 1, 0x3f800000, 0x7f800000, 0x7fc00000, 0x7f800001]),
                                        (64, [0, 1, 0x3ff0000000000000, 0x7ff0000000000000, 0x7ff8000000000000, 0x7ff0000000000001])])
def test_classes(width, values):
    assert [operand_class(v, width) for v in values] == ['zero', 'subnormal', 'normal', 'infinity', 'qnan', 'snan']
    assert operand_class(values[0] | (1 << (width - 1)), width) == 'zero'


def test_coverage_uses_pre_instruction_values_and_refuses_sticky_flags():
    rows = [dict(insn='0x13', fd_valid=True, fd=1, fd_wdata='0xffffffff3f800000', fcsr='0x0'),
            dict(insn=hex((1 << 15) | (1 << 20) | (1 << 7) | 0x53), fd_valid=True,
                 fd=1, fd_wdata='0xffffffff00000000', fcsr='0x1')]
    result = report(rows, 32)
    assert result['observed'] == 1
    assert all(hit['bin'][3:] == ['normal', 1] for hit in result['hits'])
    rows.append(dict(rows[-1]))
    assert report(rows, 32)['unknown_raised_flags'] == 1


def test_unseen_fp_registers_get_no_coverage():
    assert report([dict(insn='0x53', fcsr='0x0')], 64)['hit_bins'] == 0
