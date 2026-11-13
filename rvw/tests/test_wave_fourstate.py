"""Short VCD vectors retain unknown high bits in expression searches."""
import pytest

from rvw.wave import index, search
from rvw.wave.expr import Expr
from rvw.wave.vcd import Var

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('raw', ['bx', 'bX', 'bz', 'bZ', 'bx01', 'bz01'])
def test_short_unknown_vector_select(raw):
    variables = [Var('!', 'top.a', 8, 'wire')]
    assert Expr('a[5]', variables).evaluate({'!': raw}, {}) is None
    assert Expr('a[7:3]', variables).evaluate({'!': raw}, {}) is None


@pytest.mark.parametrize('raw', ['bx01', 'bz01', 'bX01', 'bZ01'])
def test_short_unknown_vector_keeps_known_low_bits(raw):
    variables = [Var('!', 'top.a', 8, 'wire')]
    assert Expr('a[1:0]', variables).evaluate({'!': raw}, {}) == 1


@pytest.mark.parametrize('raw', ['b1', 'b01', 'b101'])
def test_short_binary_vector_zero_extends(raw):
    assert Expr('a[5]', [Var('!', 'top.a', 8, 'wire')]).evaluate({'!': raw}, {}) == 0


@pytest.mark.parametrize('reader', ['vcd', 'rvwi'])
@pytest.mark.parametrize('raw', ['bx', 'bX', 'bz', 'bZ', 'bx01', 'bz01'])
def test_search_does_not_treat_unknown_extension_as_zero(tmp_path, reader, raw):
    source = tmp_path / 'short.vcd'
    source.write_text('$timescale 1 ns $end\n$scope module top $end\n'
                      '$var wire 8 ! a [7:0] $end\n$upscope $end\n'
                      '$enddefinitions $end\n#0\n' + raw + ' !\n#10\nb0 !\n#20\n')
    path = str(source)
    if reader == 'rvwi':
        path = str(tmp_path / 'short.rvwi')
        index.build(str(source), path)
    result = search.find(path, 'a[5] == 0')
    assert result['matches'] == [{'start': 10, 'end': None}]
    assert result['unknown_steps'] == 1
