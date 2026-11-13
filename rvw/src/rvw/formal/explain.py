"""Agent-readable dependency chains from an actual SpinalTrace dynamic graph."""


def explain(graph):
    if not isinstance(graph.get('vertices'), list) or not isinstance(graph.get('edges'), list):
        return {'schema': 'rvw.cex-explanation/1', 'status': 'incomplete', 'chain': [],
                'reason': 'SpinalTrace graph has no vertex or edge list'}
    nodes = graph['vertices']
    dependencies = [[] for _ in nodes]
    for edge in graph['edges']:
        source, target = edge['from'], edge['to']
        if type(source) is not int or type(target) is not int or not (0 <= source < len(nodes) and 0 <= target < len(nodes)):
            raise ValueError('dynamic dependency edge outside vertex list')
        dependencies[source].append({'node_id': target, 'kind': edge['kind'], 'clocked': edge['clocked']})
    accuracy = graph.get('accuracy', {'status': 'incomplete', 'reasons': ['SpinalTrace accuracy metadata missing']})
    return {'schema': 'rvw.cex-explanation/1', 'status': accuracy['status'], 'accuracy': accuracy,
            'chain': [{'node_id': i, 'source': {k: node.get(k) for k in ('file', 'line', 'char')},
                       'name': node.get('name'), 'timestamp': node.get('timestamp'),
                       'value': node.get('sim_data'), 'assigns_to': node.get('assigns_to'),
                       'causes': dependencies[i]} for i, node in enumerate(nodes)],
            'scope': 'Observed dynamic dependencies from SpinalTrace. This is not a solver proof of causality or a source repair.'}
