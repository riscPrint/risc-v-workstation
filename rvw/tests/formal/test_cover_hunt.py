from copy import deepcopy
import pytest
from rvw.formal.cover_hunt import problem

pytestmark = pytest.mark.fast


def design():
    return {'modules': {'top': {'netnames': {'a': {'bits': [2]}, 'enable': {'bits': [3]}},
        'cells': {'selected': {'type': '$cover', 'parameters': {}, 'attributes': {'src': 'test:3'},
                              'port_directions': {'A': 'input', 'EN': 'input'}, 'connections': {'A': [2], 'EN': [3]}},
                  'other_cover': {'type': '$cover', 'connections': {}}, 'original_assert': {'type': '$assert', 'connections': {}},
                  'environment': {'type': '$assume', 'connections': {'A': [3], 'EN': ['1']}},
                  'state': {'type': '$dff', 'connections': {'D': [2], 'Q': [4]}}}}}}


def test_only_selected_cover_becomes_a_negated_safety_check():
    d = design()
    original = deepcopy(d)
    r = problem(d, 'top', 'selected')['modules']['top']['cells']
    assert d == original
    assert set(r) == {'selected', '$rvw_cover_not', 'environment', 'state'}
    assert r['environment'] == d['modules']['top']['cells']['environment']
    assert r['state'] == d['modules']['top']['cells']['state']
    assert r['selected']['type'] == '$assert'
    assert r['selected']['connections']['EN'] == [3]
    assert r['selected']['connections']['A'] == r['$rvw_cover_not']['connections']['Y']
    assert r['$rvw_cover_not']['connections']['A'] == [2]


def test_command_and_mcp_registration():
    from rvw.cli import build_parser
    from rvw.formal.commands.cover_hunt import mcp_tools
    args = build_parser().parse_args(['formal', 'cover-hunt', '--manifest', 'plan.json', '--out', 'out'])
    assert args.budget == 60 and args.timeout == 15
    assert [t.name for t in mcp_tools()] == ['formal_cover_hunt']
