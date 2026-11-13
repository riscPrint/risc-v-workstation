"""Reset failures must identify the unsupported form before a solver starts."""
import pytest
from rvw.formal.security.unsupported import UnsupportedSecurity, check_properties, mapping_failure

pytestmark = pytest.mark.fast


def module(*kinds):
    return {'cells': {str(i): {'type': kind} for i, kind in enumerate(kinds)}}


def test_async_dut_assertion_has_actionable_fix():
    with pytest.raises(UnsupportedSecurity, match='sampled reset'):
        check_properties(module('$adff', '$assert'))


def test_plain_async_state_and_sync_assertion_are_not_misclassified():
    check_properties(module('$adff'))
    check_properties(module('$dff', '$assert'))


def test_mapping_reset_error_retains_native_diagnostic():
    with pytest.raises(UnsupportedSecurity, match='Multiple edge sensitive events'):
        mapping_failure('ERROR: Multiple edge sensitive events found for this signal!')
    mapping_failure('ERROR: syntax error')
