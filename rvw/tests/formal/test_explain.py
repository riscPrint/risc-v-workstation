import pytest
from rvw.formal.explain import explain


def test_dynamic_causes_keep_source_time_and_accuracy():
    graph = {'accuracy': {'status': 'approximate', 'reasons': ['partial writes']},
             'vertices': [{'name': 'fail', 'timestamp': 20, 'file': 'A.scala', 'line': 5, 'sim_data': '0'},
                          {'name': 'input', 'timestamp': 10, 'sim_data': '1'}],
             'edges': [{'from': 0, 'to': 1, 'kind': 'Data', 'clocked': True}]}
    result = explain(graph)
    assert result['status'] == 'approximate'
    assert result['chain'][0]['causes'][0]['node_id'] == 1
    assert result['chain'][1]['timestamp'] == 10
    assert result['chain'][0]['source']['line'] == 5


def test_missing_accuracy_is_incomplete():
    assert explain({'vertices': [], 'edges': []})['status'] == 'incomplete'


def test_unknown_edge_is_not_a_chain():
    with pytest.raises(ValueError, match='outside'):
        explain({'vertices': [], 'edges': [{'from': 0, 'to': 2, 'kind': 'Data', 'clocked': False}]})


def test_missing_graph_does_not_claim_an_explanation():
    result = explain({})
    assert result['status'] == 'incomplete' and result['chain'] == []
