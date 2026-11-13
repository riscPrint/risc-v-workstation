"""Reset refusal and conservative unknown constants for new core RTL."""
import pytest
from rvw.formal.security.ift import instrument
pytestmark = pytest.mark.fast


def netlist(value='x'):
    return {'modules': {'dut': {'ports': {'result': {'direction': 'output', 'bits': [value]}}, 'netnames': {'result': {'bits': [value]}}, 'cells': {}}}}


@pytest.mark.parametrize('value', ['x', 'z'])
def test_unknown_constant_has_both_values(value):
    text = instrument(netlist(value), 'dut')
    assert "assign result[0] = 1'b0" in text
    assert "assign result__t[0] = 1'b1" in text


def test_async_refusal_has_shared_configuration_hint():
    design = netlist('0')
    design['modules']['dut']['cells']['ff'] = {'type': '$_DFF_PP0_'}
    with pytest.raises(ValueError, match='Elaboration.config.*SpinalDB'):
        instrument(design, 'dut')


def test_autocheck_exposes_event_reset_flags():
    from rvw.formal.apps_mcp import mcp_tools
    tool = next(t for t in mcp_tools() if t.name == 'formal_autocheck')
    assert {'event_model', 'async_reset'} <= tool.input_schema['properties'].keys()


def test_unused_netname_slice_needs_no_driver():
    design = netlist('0')
    design['modules']['dut']['netnames']['temporary'] = {'bits': [999]}
    text = instrument(design, 'dut')
    assert 'n999' not in text


def test_live_undriven_output_is_still_refused():
    with pytest.raises(ValueError, match='undriven bits'):
        instrument(netlist(999), 'dut')


def test_shadow_prefix_matches_live_bit_instrumentation():
    from rvw.sec.ift import shadow
    design = {'modules': {'dut': {'ports': {
        'clk': {'direction':'input','bits':[3]},
        'reset': {'direction':'input','bits':[4]},
        'n999': {'direction':'input','bits':[2]},
        'result': {'direction':'output','bits':[2]}},
        'netnames': {'clk':{'bits':[3]}, 'reset':{'bits':[4]},
                     'n999':{'bits':[2]}, 'result':{'bits':[2]}, 'unused':{'bits':[999]}},
        'cells': {}}}}
    text, prefix = shadow(design,'dut',dict(clock='clk',reset='reset',sources=['n999'],sinks=['result']))
    assert prefix == ''
    assert "assign t2 = 1'b1;" in text
    assert '_t2' not in text
