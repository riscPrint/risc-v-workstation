"""A workload report from the existing profile, sensitivity and DSE engines."""
from dataclasses import asdict
import json
from pathlib import Path
from .project import configuration
from .regions import profile
from .sensitivity import sensitivity
from .search import search


def report(plan, out):
    plan = Path(plan).resolve()
    spec = json.loads(plan.read_text())
    if spec.get('schema') != 'rvw.ooo-designer-plan/1':
        raise ValueError('expected rvw.ooo-designer-plan/1')
    config = (plan.parent/spec['config']).resolve()
    workloads = spec['workloads']
    if not workloads or len({w['id'] for w in workloads}) != len(workloads):
        raise ValueError('workload ids must be nonempty and unique')
    dest = Path(out).resolve()
    dest.mkdir(parents=True, exist_ok=False)
    traces, rows = [], []
    for w in workloads:
        trace = str((plan.parent/w['trace']).resolve())
        traces.append(trace)
        elf = str((plan.parent/w['elf']).resolve()) if w.get('elf') else None
        p = profile(config, trace, elf=elf, max_cycles=spec.get('max_cycles',1000000))
        rows.append(dict(id=w['id'], **p))
    common = dict(config=str(config), traces=traces, max_cycles=spec.get('max_cycles',1000000))
    sp = dest/'sensitivity-plan.json'
    sp.write_text(json.dumps(dict(schema='rvw.ooo-sensitivity-plan/1', **common,
                                 parameters=spec['sensitivity_parameters'])))
    ranking = sensitivity(sp, dest/'sensitivity.json')
    dp = dest/'search-plan.json'
    dp.write_text(json.dumps(dict(schema='rvw.ooo-search-plan/1', **common,
                                 parameters=spec['search_parameters'],method='grid',
                                 budget=spec.get('budget',16))))
    dse = search(dp, dest/'search')
    base = asdict(configuration(json.loads(config.read_text())))
    def at(data, path):
        for key in path.split('.'):
            data = data[key]
        return data
    changes = []
    baseline = ranking['baseline']['cycles']
    for point in sorted(dse['points'],key=lambda p:(p['cycles'],p['id'])):
        delta = {key:dict(before=at(base,key),after=at(point['config'],key))
                 for key in spec['search_parameters'] if at(base,key)!=at(point['config'],key)}
        if not delta or point['cycles'] >= baseline:
            continue
        changes.append(dict(changes=delta, cycles=point['cycles'],
                            speedup=baseline/point['cycles'],point=point['id']))
        if len(changes)==3:
            break
    cycles, instret = sum(r['cycles'] for r in rows),sum(r['instret'] for r in rows)
    result = dict(schema='rvw.ooo-designer/1',evidence='model-only',accuracy_status='inconclusive',
                  cycles=cycles,instret=instret,ipc=instret/cycles,workloads=rows,
                  bottlenecks=ranking['ranking'],next_three_changes=changes,
                  recommendation_status='reported' if len(changes)==3 else 'fewer_than_three_improving_points',
                  limits=['model slot attribution is not measured hardware top-down analysis',
                          'sensitivity is local; search uses fixed committed paths',
                          'recommendations rank declared candidate points, not physical feasibility'])
    (dest/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    text = ['# Designer report','',f'Model IPC: {result["ipc"]:.4f}. Evidence: model-only.',
            '', '| Workload | Instructions | Cycles | IPC |','|---|---:|---:|---:|']
    for r in rows:
        text.append(f'| {r["id"]} | {r["instret"]} | {r["cycles"]} | {r["ipc"]:.4f} |')
    for r in rows:
        text.extend(['', f'## Functions in {r["id"]}', '', '| Function | Retiring | Front end | Bad speculation | Memory | Core |',
                     '|---|---:|---:|---:|---:|---:|'])
        for name, region in r['attribution']['regions'].items():
            f = region['fractions']
            label = name.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('|',r'\|')
            text.append('| '+label+' | '+' | '.join(f'{f[k]:.1%}' for k in
                ('retiring','frontend_bound','bad_speculation','backend_memory_bound','backend_core_bound'))+' |')
        text.append('')
    text.extend(['','## Structures to inspect',''])
    text.extend(f'- {r["parameter"]}: elasticity {r["sensitivity"]}.' for r in ranking['ranking'][:5])
    text.extend(['','## Next three changes to try',''])
    text.extend(f'- {json.dumps(c["changes"],sort_keys=True)}: model speedup {c["speedup"]:.3f}.' for c in changes)
    if len(changes)<3:
        text.append('The declared search found fewer than three improving points.')
    text.extend(['','Model results need RTL checks. Function rows use ELF symbols when supplied.'])
    (dest/'report.md').write_text('\n'.join(text)+'\n')
    return result
