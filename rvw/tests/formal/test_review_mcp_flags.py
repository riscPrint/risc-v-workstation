"""Boolean MCP options must reach argparse as flags."""
import pytest
from rvw.cli import build_parser
from rvw.formal.mcp_tools import _argv

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('command,options,flag', [
    ('isa', dict(out='out'), 'unbounded'),
    ('machine-checks', dict(manifest='plan.json', out='out'), 'run'),
    ('datapath', dict(unit='mul', out='out'), 'confirm'),
])
def test_mcp_boolean_option_has_no_value(command, options, flag):
    parsed = build_parser().parse_args(_argv(command, {**options, flag: True})[3:])
    assert getattr(parsed, flag) is True
