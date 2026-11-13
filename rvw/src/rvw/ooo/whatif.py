"""Change one explicit project parameter and compare the same complete C2 path."""
from copy import deepcopy
import json
from pathlib import Path
from .core import run
from .project import configuration
from .search import set_value


def what_if(config, trace, parameter, value, out, max_cycles=1000000):
    source = Path(config).resolve()
    base = json.loads(source.read_text())
    changed = deepcopy(base)
    set_value(changed, parameter, value)
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
    result = dict(schema='rvw.ooo-what-if/1',evidence='model-only',accuracy_status='inconclusive',
                  parameter=parameter,value=value,baseline=a,candidate=b,
                  delta=dict(cycles=b['cycles']-a['cycles'],ipc=b['ipc']-a['ipc'],
                             relative_ipc=b['ipc']/a['ipc']-1,speedup=a['cycles']/b['cycles'],
                             events={k:b['events'].get(k,0)-a['events'].get(k,0)
                                     for k in sorted(a['events'].keys()|b['events'].keys())}),
                  limits=['same committed path; program changes are not predicted',
                          'positive cycle delta means slower; positive IPC delta means faster',
                          'no RTL or physical PPA estimate'])
    (dest/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
