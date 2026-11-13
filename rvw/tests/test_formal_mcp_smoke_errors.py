import json
from argparse import Namespace
from pathlib import Path
import pytest

pytestmark = pytest.mark.fast


def test_unknown_scenario_backend_names_choices():
    from rvw.formal.scenario import plan
    with pytest.raises(ValueError, match='backend.*baremetal'):
        plan({'schema': 'rvw.scenario/1', 'backends': {'baremetal': {}}, 'resources': {}, 'actions': [{'id': 'read', 'kind': 'read32'}]}, 'rtl')


class Job:
    def __init__(self, lines=(), code=2): self.lines, self.code = lines, code
    def run(self, argv): self.argv = argv; return self.code
    def tail(self, n): return self.lines[-n:]


def test_liveness_missing_report_is_actionable(tmp_path):
    from rvw.formal.mcp_tools import _liveness
    from rvw.mcp.spec import ToolError
    job = Job([json.dumps({'error': 'unsupported property: use a clocked assertion', 'hint': 'Supply clocked SVA.'})], code=0)
    result = _liveness(job, source='counter.sv', top='counter', out=str(tmp_path))
    assert 'unsupported property' in result['error']
    assert '--json' in job.argv
    assert result['hint'] == 'Supply clocked SVA.'


def test_sva_inspection_accepts_parsed_status(tmp_path):
    from rvw.formal.mcp_tools import _runner
    (tmp_path/'result.json').write_text(json.dumps({'status':'parsed', 'properties':[{'id':'p'}]}))
    assert _runner('sva-inspect')(Job(code=0), out=str(tmp_path))['status']=='parsed'


def test_formal_error_preserves_json_diagnostic(tmp_path):
    from rvw.formal.mcp_tools import _runner
    from rvw.mcp.spec import ToolError
    job=Job([json.dumps({'error':'set RVW_SLANG or pass --plugin', 'hint':'Supply --plugin PATH.'})])
    result = _runner('sva-inspect')(job, out=str(tmp_path))
    assert 'RVW_SLANG' in result['error']
    assert '--json' in job.argv
    assert result['hint']=='Supply --plugin PATH.'
