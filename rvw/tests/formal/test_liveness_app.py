import pytest
from rvw.formal.liveness_app import state_bits, monitor


def test_full_state_and_refusal():
    module = {'netnames': {'q': {'bits': [2,3]}}, 'cells': {'q': {'type': '$dff', 'parameters': {'CLK_POLARITY': '1'}, 'connections': {'Q': [2,3]}}}}
    assert len(state_bits(module)) == 2
    module['cells']['q']['type'] = '$adff'
    with pytest.raises(ValueError, match='unsupported state'):
        state_bits(module)


def test_nonempty_fair_loop_retains_request():
    text = monitor(['q'], 'req', 'ack', ['ready'], 'clk', 'reset')
    assert 'rvwl_snapshot <= {q}' in text
    assert 'rvwl_pending || (req)' in text
    assert '&& (rvwl_fair0)' in text
    assert 'if (ack) rvwl_tracking <= 0' in text


def test_native_fair_response(tmp_path):
    import json
    import shutil
    from argparse import Namespace
    from rvw.formal.liveness_app import run
    if not all(shutil.which(t) for t in ('yosys', 'sby', 'z3')):
        pytest.skip('native Yosys/SBY/Z3 required')
    plan = {'schema': 'rvw.liveness-app/1', 'top': 'top', 'clock': 'clk', 'reset': 'reset',
            'verilog': ['top.sv'], 'request': 'req', 'response': 'ack', 'fairness': ['ready']}
    (tmp_path/'plan.json').write_text(json.dumps(plan))
    for name, update, expected in [('good', '(pending || req) && ready', 'pass'), ('bad', "1'b0", 'fail')]:
        (tmp_path/'top.sv').write_text('module top(input clk, reset, req, ready, output reg ack); reg pending;\n'
            'always @(posedge clk) if (reset) begin pending<=0; ack<=0; end else begin\n'
            f'pending <= (pending || req) && !ack; ack <= {update}; end endmodule')
        out = tmp_path/name
        run(Namespace(manifest=str(tmp_path/'plan.json'), out=str(out), depth=12, engine='abc:pdr', timeout=20, mode='prove', json=False))
        assert json.loads((out/'result.json').read_text())['status'] == expected
