import pytest
from rvw.sim.backends import require


def test_x_requires_four_state():
    assert require('icarus', ['xz_values']).values == '4-state'
    with pytest.raises(ValueError, match='xz_values'):
        require('verilator', ['xz_values'])


@pytest.mark.parametrize('backend', ['icarus', 'verilator'])
@pytest.mark.parametrize('feature', ['sva', 'coverage', 'pessimistic_xprop', 'typo'])
def test_unknown_or_unprovided_features_refused(backend, feature):
    with pytest.raises(ValueError, match=feature):
        require(backend, [feature])


def test_unknown_backend_refused():
    with pytest.raises(ValueError, match='unsupported backend'):
        require('questa')
