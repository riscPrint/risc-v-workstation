import pytest
from rvw.formal.fair_live import check, components


def model(edges):
    return {'states': {str(i): {'x': i} for i in range(3)}, 'initial': ['0'],
            'edges': edges, 'properties': {'safe': []}}


def test_fairness_removes_environment_stutter():
    m = model([['0', '0'], ['0', '1'], ['1', '0']])
    assert check(m, ['1'])['status'] == 'fail'
    r = check(m, ['1'], [['1']])
    assert r['status'] == 'pass'
    assert r['proof_kind'] == 'finite_graph_fair_liveness'


def test_generalized_fair_cycle_can_visit_distinct_states():
    m = model([['0', '1'], ['1', '0']])
    r = check(m, ['2'], [['0'], ['1']])
    assert r['status'] == 'fail'
    assert r['counterexample_components'] == [['0', '1']]


def test_unreachable_and_infeasible_fairness_are_not_passes():
    m = model([['0', '0'], ['2', '2']])
    assert check(m, ['0'], [['2']])['status'] == 'inconclusive'
    assert check(m, ['0'], [[]])['status'] == 'inconclusive'
    assert check(model([]), ['0'])['deadlocks'] == ['0']
    with pytest.raises(ValueError):
        check(m, ['missing'])


def test_large_graph_avoids_recursion_limit():
    graph = {str(i): {str((i+1) % 4000)} for i in range(4000)}
    assert len(list(components(graph))[0]) == 4000


def test_cli_preserves_graph_and_mcp(tmp_path, capsys):
    import json
    from rvw.cli import main
    from rvw.formal.deep_cli import mcp_tools
    m = model([['0', '1'], ['1', '0']])
    m.update(progress=['1'], fairness=[['1']])
    source = tmp_path / 'model.json'
    source.write_text(json.dumps(m))
    out = tmp_path / 'out'
    assert main(['formal', 'model-live', '--manifest', str(source), '--out', str(out), '--json']) == 0
    assert 'finite_graph_fair_liveness' in capsys.readouterr().out
    assert (out / 'model.json').read_bytes() == source.read_bytes()
    assert {'formal_model_live', 'formal_swarm'} <= {t.name for t in mcp_tools()}
