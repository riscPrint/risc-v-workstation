"""Client errors cannot produce a passing interop summary or all-pass C3."""
import json
import pytest
from rvw.debug import interop

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('returncode,timed_out', [(1, False), (0, True)])
def test_client_failure_after_check_markers_remains_unresolved(tmp_path, returncode, timed_out):
    output = '\n'.join(['RVW_CONNECTED', *['RVW_CHECK:' + c for c in interop.CHECKS], 'RVW_COMPLETE'])
    result = interop.assess(output, returncode, timed_out, expect_reset=False)
    assert result['status'] != 'pass'
    result.update(openocd_version='test', target='model')
    interop.write_c3(result, tmp_path)
    tests = json.loads((tmp_path / 'results.json').read_text())['tests']
    assert any(t['status'] != 'pass' for t in tests)
