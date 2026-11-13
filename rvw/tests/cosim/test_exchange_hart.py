"""Spike commit-log hart identity must agree with the C2 extension."""
import pytest
from rvw.cosim.exchange import export, import_stream
from test_state import fixture

pytestmark = pytest.mark.fast


def test_spike_hart_must_agree_with_c2():
    header, row = fixture()
    encoded = export([header, row], 'spike')
    with pytest.raises(ValueError, match='conflict'):
        import_stream(encoded.replace('core   0:', 'core   1:', 1), 'spike')
