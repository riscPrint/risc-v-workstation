"""Provider declarations must stay beside registrations, with inventory names."""
import pytest
from rvw.doctor.inventory import load
from rvw.mcp.registry import Registry

pytestmark = pytest.mark.fast


@pytest.fixture(scope='module')
def registry():
    result, problems = Registry.discover()
    assert not problems
    return result


def test_declared_native_tools_use_inventory_names(registry):
    known = {tool['name'] for tool in load()['tools']}
    for tool in registry.tools.values():
        if tool.native_tools is not None:
            assert set(tool.native_tools) <= known, tool.name


@pytest.mark.parametrize('name', [
    'bugmem_add', 'bugmem_match', 'bugmem_list', 'bugmem_evaluate',
    'perf_report', 'perf_compare', 'probes_list', 'probes_summary',
    'probes_convert', 'checks_generate', 'checks_report',
    'verification_plan_generate', 'verification_plan_check',
    'vip_list', 'vip_buses', 'vip_bench', 'lsp_request',
])
def test_data_provider_declarations(name, registry):
    tool = registry.tools[name]
    assert tool.side_effects
    assert tool.native_tools == ()
