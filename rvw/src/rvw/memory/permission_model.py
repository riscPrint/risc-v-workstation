"""Load the finite permission projection used by generated TL-C monitors."""
import hashlib
import runpy
from rvw.runs.result import tools_root


def load():
    path = tools_root()/'SpinalChecks/coherence/model.py'
    if not path.is_file():
        raise ValueError('finite coherence model is missing from RVW_ROOT')
    code = path.read_bytes()
    model = runpy.run_path(str(path))
    report, graph = model['explore']()
    if report.get('verdict') != 'pass':
        raise ValueError('permission projection requires an exhausted unmutated model')
    states, edges = model['relation'](graph)
    if not states or not edges or any(len(p) != 2 or any(x not in (0, 1, 2) for x in p) for p in states):
        raise ValueError('unsupported coherence permission alphabet or client count')
    if any(a not in states or b not in states for a, b in edges):
        raise ValueError('coherence projection edge has an unknown state')
    return {'source_sha256': hashlib.sha256(code).hexdigest(),
            'model_states': report['states'], 'model_edges': report['edges'],
            'states': [list(p) for p in sorted(states)],
            'edges': [[list(a), list(b)] for a, b in sorted(edges)],
            'scope': 'permission projection only; not channel/data refinement'}
