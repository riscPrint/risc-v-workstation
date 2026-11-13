"""Feature requirements cannot silently select an unqualified profile."""
import pytest
from rvw.sim.uvm_features import SUPPORTED, UNSUPPORTED, require, markdown


def test_supported_profile():
    require(SUPPORTED)


@pytest.mark.parametrize('feature', UNSUPPORTED)
def test_unsupported_names_diagnostic_and_workaround(feature):
    diagnostic, workaround = UNSUPPORTED[feature]
    with pytest.raises(ValueError, match=diagnostic) as exc:
        require([feature])
    assert workaround in str(exc.value)


def test_unknown_is_not_assumed_supported():
    with pytest.raises(ValueError, match='unsupported:uvm_unknown_feature'):
        require(['future_feature'])
    assert len(markdown().splitlines()) == len(UNSUPPORTED)+2


def test_runner_refuses_before_tool_or_output(tmp_path):
    from rvw.sim import uvm
    with pytest.raises(ValueError, match='unsupported:uvm_four_state'):
        uvm.run(tmp_path/'out', required_features=['four_state'])
    assert not (tmp_path/'out').exists()
