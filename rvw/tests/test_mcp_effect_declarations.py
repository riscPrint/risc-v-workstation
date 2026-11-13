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


def test_query_declarations(registry):
    tools = [tool for name, tool in registry.tools.items() if name.startswith('query_')]
    assert tools
    assert all(tool.side_effects is not None and tool.native_tools is not None for tool in tools)
    assert registry.tools['query_info'].side_effects == 'read-only'
    assert registry.tools['query_info'].native_tools == ()
    assert registry.tools['query_build_db'].native_tools == ('JDK', 'sbt')
    assert set(registry.tools['query_build_hdl'].native_tools) == {'Yosys', 'yosys-slang', 'GHDL', 'firtool'}
    assert 'writes' in registry.tools['query_export'].side_effects


def test_wave_declarations_include_conditional_cache_writes(registry):
    tools = [tool for name, tool in registry.tools.items() if name.startswith('wave_')]
    assert tools
    assert all(tool.side_effects and tool.native_tools is not None for tool in tools)
    assert 'index cache' in registry.tools['wave_changes'].side_effects
    assert 'out' in registry.tools['wave_cut'].side_effects
    assert registry.tools['wave_index_verify'].side_effects == 'read-only'
    assert registry.tools['wave_session_open'].native_tools == ('GTKWave tools',)


def test_formal_declarations(registry):
    tools = [tool for name, tool in registry.tools.items() if name.startswith('formal_')]
    assert tools
    assert all(tool.side_effects and tool.native_tools is not None for tool in tools)
    assert registry.tools['formal_csr'].native_tools == ()
    assert registry.tools['formal_doctor'].native_tools == ()
    assert 'EQY' in registry.tools['formal_equiv'].native_tools
    assert registry.tools['formal_sail_state'].native_tools == ('Sail',)
