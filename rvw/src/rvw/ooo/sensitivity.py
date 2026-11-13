"""One-at-a-time finite differences. No optimization or RTL fidelity verdict."""
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import json
import math
from pathlib import Path
from rvw.arch.ledger import store
from .core import Config, _instructions, simulate
from .project import configuration
from .search import set_value


def numeric(data, prefix=''):
    for key, value in data.items():
        name = f'{prefix}.{key}' if prefix else key
        if isinstance(value, dict):
            yield from numeric(value, name)
        elif type(value) in (int, float) and value > 0:
            yield name, value


def sensitivity(plan, out, project=None):
    if project is not None:
        from rvw.common.project import load_project
        load_project(project)
    p = Path(plan).resolve()
    spec = json.loads(p.read_text())
    if spec.get('schema') != 'rvw.ooo-sensitivity-plan/1':
        raise ValueError('expected sensitivity plan')
    fraction = spec.get('fraction', 0.1)
    if type(fraction) not in (int,float) or not math.isfinite(fraction) or not 0 < fraction < 1:
        raise ValueError('fraction must be in (0,1)')
    cp = p.parent/spec['config']
    base = asdict(configuration(json.loads(cp.read_text())))
    fields = dict(numeric(base))
    selected = spec.get('parameters', sorted(fields))
    if not isinstance(selected,list) or not selected or len(set(selected)) != len(selected) or any(k not in fields for k in selected):
        raise ValueError('parameters must select unique positive numeric fields')
    if len(selected)>128:
        raise ValueError('at most 128 parameter paths are supported')
    paths = [p.parent/t for t in spec['traces']]
    if not paths or len(set(paths)) != len(paths):
        raise ValueError('traces must be nonempty and unique')
    traces = [_instructions(t.read_bytes(),base['custom_instructions']) for t in paths]
    hashes = {str(t):sha256(t.read_bytes()).hexdigest() for t in paths}
    budget = spec.get('max_cycles',1000000)
    def evaluate(data):
        config = Config(**data)
        runs = [simulate(ops,config,budget) for ops in traces]
        cycles, instructions = sum(r['cycles'] for r in runs), sum(r['instret'] for r in runs)
        return dict(cycles=cycles, instret=instructions, ipc=instructions/cycles,
                    traces=[dict(trace=str(t),cycles=r['cycles'],ipc=r['ipc']) for t,r in zip(paths,runs)])
    baseline = evaluate(base)
    rows = []
    for key in selected:
        value=fields[key]
        step=max(1,round(value*fraction)) if type(value) is int else value*fraction
        trials=[]
        for candidate in (value-step,value+step):
            data=deepcopy(base)
            set_value(data,key,candidate)
            try:
                r=evaluate(data)
                r.update(value=candidate,status='reported',
                         relative_ipc_change=r['ipc']/baseline['ipc']-1,
                         elasticity=(r['ipc']/baseline['ipc']-1)/(candidate/value-1))
            except ValueError as exc:
                r=dict(value=candidate,status='unsupported',reason=str(exc))
            trials.append(r)
        valid=[r for r in trials if r['status']=='reported']
        rows.append(dict(parameter=key,baseline_value=value,trials=trials,
                         sensitivity=max((abs(r['elasticity']) for r in valid),default=None),
                         best_ipc_gain=max((r['relative_ipc_change'] for r in valid),default=None)))
    rows.sort(key=lambda r:(r['sensitivity'] is None,-(r['sensitivity'] or 0),r['parameter']))
    return store(out,dict(schema='rvw.ooo-sensitivity/1',status='reported',
                         config_sha256=sha256(cp.read_bytes()).hexdigest(),trace_sha256=hashes,
                         fraction=fraction,baseline=baseline,ranking=rows,
                         method='one parameter at a time; instruction-pooled IPC; rank absolute finite-difference elasticity',
                         limits=['local effects only; parameter interactions are not explored',
                                 'zero-valued switches and lists are not perturbed',
                                 'invalid candidates remain explicit; no RTL accuracy established']))
