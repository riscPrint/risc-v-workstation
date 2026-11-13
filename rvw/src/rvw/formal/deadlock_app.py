"""Exact progress-possibility checks for an explicit finite transition graph."""
import json
from pathlib import Path
from .fair_live import components


def check(model):
    states = set(model['states'])
    initial, progress = set(model['initial']), set(model['progress'])
    fairness = [set(f) for f in model.get('fairness', [])]
    if not states or not initial or not initial <= states or not progress <= states or any(not f <= states for f in fairness):
        raise ValueError('initial, progress and fairness sets need known states')
    edges = {s:set() for s in states}
    reverse = {s:set() for s in states}
    for a,b in model['edges']:
        if a not in states or b not in states: raise ValueError('unknown transition endpoint')
        edges[a].add(b); reverse[b].add(a)
    def closure(seed, graph):
        seen, pending = set(seed), list(seed)
        while pending:
            for t in graph[pending.pop()] - seen:
                seen.add(t); pending.append(t)
        return seen
    reachable = closure(initial, edges)
    fair_cycles = [part for part in components(edges) if (len(part)>1 or any(s in edges[s] for s in part)) and all(part & f for f in fairness)]
    # With justice, a path to progress must admit a fair infinite suffix.
    admissible = closure(set().union(*fair_cycles), reverse) if fairness else states
    possible = closure(progress & admissible, reverse)
    bad = reachable & admissible - possible
    infeasible = reachable - admissible
    status = 'fail' if bad else 'inconclusive' if infeasible else 'pass'
    return dict(schema='rvw.deadlock-app/1', status=status,
        proof_kind='finite_graph_progress_possibility' if status=='pass' else 'none',
        reachable=sorted(reachable), progress_impossible=sorted(bad), no_fair_continuation=sorted(infeasible),
        terminal_states=sorted(s for s in reachable if not edges[s]),
        fairness=[sorted(f) for f in fairness], progress=sorted(progress),
        limits='Exact supplied finite graph only. Checks AG EF progress with an admissible fair suffix when justice is declared. No RTL-to-graph translation claim. This is not universal eventual response.')


def run(args):
    from rvw.common.capture import Capture
    from .common import write_json
    out=Path(args.out).resolve(); out.mkdir(parents=True,exist_ok=False)
    capture=Capture(out/'inputs')
    model=json.loads(capture.file(Path(args.manifest)).copy.read_text())
    report=check(model); report['input_capture']=capture.record()
    write_json(out/'result.json',report)
    print(json.dumps(report,indent=2) if args.json else report['status'])
    return 0 if report['status']=='pass' else 1
