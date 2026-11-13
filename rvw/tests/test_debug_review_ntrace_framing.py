"""Malformed complete messages produce codec errors rather than tool crashes."""
import pytest
from rvw.debug import ntrace, ntrace_check

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('name', ['IndirectBranch', 'ProgTraceSync', 'Error', 'ProgTraceCorrelation'])
def test_message_ending_inside_fixed_header_is_rejected(name):
    data = bytes([(ntrace.TCODES[name] << 2) | 3])
    with pytest.raises(ValueError):
        ntrace.unpack(data, ntrace.normalize())


def test_short_vendor_vector_is_a_failed_vector():
    result = ntrace_check.verify_vectors([{'bytes': '13', 'messages': [{'tcode': 'IndirectBranch'}]}],
                                         ntrace.normalize())
    assert result[0]['status'] == 'fail'
