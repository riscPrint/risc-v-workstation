"""Change one explicit project parameter and compare the same complete C2 path."""
from copy import deepcopy
import json
from hashlib import sha256
from pathlib import Path
from .core import run
from .project import configuration
from .search import set_value


def what_if(config, trace, parameter, value, out, max_cycles=1000000):
    source = Path(config).resolve()
    original = source.read_bytes()
    base = json.loads(original)
    changed = deepcopy(base)
    node = changed
    parts = parameter.split('.')
    try:
        for part in parts[:-1]:
            node = node[part]
        old = node[parts[-1]]
    except (KeyError, TypeError):
        raise ValueError(f'Unknown timing parameter {parameter!r}. Select an existing scalar '
                         'in the model config; see docs/INTEGRATION_GUIDE.md#project-input-recipes.') from None
    if type(old) in (int, float):
        set_value(changed, parameter, value)
    elif type(old) in (bool, str) and type(value) is type(old):
        node[parts[-1]] = value
    else:
        raise ValueError('parameter must be an existing scalar with the same type')
    configuration(base)
    configuration(changed)
    dest = Path(out).resolve()
    dest.mkdir(parents=True, exist_ok=False)
    baseline_path, candidate_path = dest/'baseline-config.json',dest/'candidate-config.json'
    baseline_path.write_text(json.dumps(base,indent=2)+'\n')
    candidate_path.write_text(json.dumps(changed,indent=2)+'\n')
    a,b = run(baseline_path,trace,max_cycles),run(candidate_path,trace,max_cycles)
    if a['trace_sha256'] != b['trace_sha256']:
        raise ValueError('trace changed between baseline and candidate')
    result = dict(schema='rvw.ooo-what-if/1',status='reported',evidence='model-only',accuracy_status='inconclusive',
                  source_config_sha256=sha256(original).hexdigest(),
                  parameter=parameter,baseline_value=old,value=value,baseline=a,candidate=b,
                  delta=dict(cycles=b['cycles']-a['cycles'],ipc=b['ipc']-a['ipc'],
                             relative_ipc=b['ipc']/a['ipc']-1,speedup=a['cycles']/b['cycles'],
                             events={k:b['events'].get(k,0)-a['events'].get(k,0)
                                     for k in sorted(a['events'].keys()|b['events'].keys())}),
                  limits=['same committed path; program changes are not predicted',
                          'positive cycle delta means slower; positive IPC delta means faster',
                          'no RTL or physical PPA estimate'])
    (dest/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    (dest/'report.md').write_text(
        '# Parameter comparison\n\n'
        f'Change `{parameter}` from `{json.dumps(old)}` to `{json.dumps(value)}`.\n\n'
        '| Metric | Baseline | Candidate | Delta |\n|---|---:|---:|---:|\n'
        f"| Cycles | {a['cycles']} | {b['cycles']} | {result['delta']['cycles']:+d} |\n"
        f"| IPC | {a['ipc']:.6f} | {b['ipc']:.6f} | {result['delta']['ipc']:+.6f} |\n\n"
        f"Speedup: {result['delta']['speedup']:.6f}x.\n\n"
        'The model runs use the same committed path. RTL accuracy remains inconclusive.\n')
    return result
