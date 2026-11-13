import pytest
from rvw.formal.aiger_input import to_verilog


def test_legacy_latch_and_output():
    text = to_verilog(b'aag 2 1 1 1 0\n2\n4 2 4\n4\n', 'top')
    assert 'always @($global_clock) n2 <= n1' in text
    assert 'initial n2' not in text
    assert 'assert(!(n2))' in text


def test_extended_constraints():
    text = to_verilog(b'aag 1 1 0 0 0 1 1 0 0\n2\n3\n2\n', 'top')
    assert 'assume(n1)' in text
    assert 'assert(!(~n1))' in text


def test_binary_and_gate():
    text = to_verilog(b'aig 2 1 0 1 1\n4\n' + bytes([2, 0]), 'top')
    assert 'wire n2 = n1 & n1;' in text


@pytest.mark.parametrize('data', [b'aag 0 0 0 0 0\n', b'aag 0 0 0 0 0 0 0 1 0\n',
                                  b'aag 1 0 0 1 0\n2\n', b'aig 2 1 0 1 1\n4\n'])
def test_reject_incomplete_or_unsupported(data):
    with pytest.raises(ValueError):
        to_verilog(data, 'top')
