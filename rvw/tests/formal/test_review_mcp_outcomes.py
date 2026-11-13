"""Command-specific successful observations remain usable through MCP."""
import json
import pytest
from rvw.formal.mcp_tools import _runner

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('command,status', [
    ('equiv-partitions', 'equivalent'), ('cover-hunt', 'covered'),
    ('trace-mine', 'candidates'), ('trace-mine', 'no_candidates'),
    ('scenario-compile', 'generated'),
])
def test_successful_command_result_is_returned(tmp_path, command, status):
    result = dict(status=status)
    (tmp_path / 'result.json').write_text(json.dumps(result))
    class Job:
        def run(self, argv):
            return 0
        def tail(self, count):
            return []
    assert _runner(command)(Job(), out=str(tmp_path)) == result


def test_wrong_success_status_is_still_rejected(tmp_path):
    from rvw.mcp.spec import ToolError
    (tmp_path / 'result.json').write_text(json.dumps(dict(status='pass')))
    class Job:
        def run(self, argv):
            return 0
        def tail(self, count):
            return []
    with pytest.raises(ToolError, match='disagree'):
        _runner('cover-hunt')(Job(), out=str(tmp_path))
