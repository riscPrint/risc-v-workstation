"""Bounded external evidence clients using the existing trial transport and recorder."""
import copy
import hashlib
import json
from pathlib import Path

from rvw.mcp.registry import Registry
from rvw.mcp.spec import ToolSpec, schema
from .engine import report
from .solver import WORKFLOW, locations, rank


class ToolSession:
    def __init__(self, task, max_calls=32):
        self.task, self.max_calls = task, max_calls
        self.finished = self.claimed = self.evidence_timed_out = False
        self.outcome = 'inconclusive'
        self.requests = []

    def inspect(self):
        return {'id': self.task['id'], 'steps': copy.deepcopy(self.task['steps']),
                'max_calls': max(1, self.max_calls - 2),
                'budget_s': max(0.1, self.task['budget_s'] - 5)}

    def finish(self, claimed_fix, outcome='inconclusive', timed_out=False):
        self.finished, self.claimed = True, claimed_fix
        self.outcome, self.evidence_timed_out = outcome, timed_out
        return {'finished': True}

    def registry(self):
        from rvw.regress.mcp_tools import mcp_tools as regress
        from rvw.cosim.mcp_tools import mcp_tools as cosim
        from rvw.bundle.mcp_tools import mcp_tools as bundle
        from rvw.query.mcp_tools import mcp_tools as query
        from rvw.wave.mcp_tools import mcp_tools as wave
        tools = [t for factory in (regress, cosim, bundle, query, wave)
                 for t in factory() if t.name in (*WORKFLOW, 'wave_find', 'wave_info')]
        tools += [ToolSpec('bench_inspect', 'Read public evidence workflow inputs. No evaluator truth is returned.',
                           schema({}), self.inspect),
                  ToolSpec('bench_finish', 'Finish the evidence trial. No source repair or independent check is granted.',
                           schema({'claimed_fix': {'type': 'boolean'}, 'outcome': {'type': 'string'},
                                   'timed_out': {'type': 'boolean'}}, ['claimed_fix']), self.finish)]
        return Registry(tools)

    def score(self):
        candidates = locations([r.get('result', {}) for r in self.requests
                                if r['tool'] in ('query_drivers', 'wave_why')])
        returned = set()
        for request in self.requests:
            result = request.get('result')
            if request['tool'] not in WORKFLOW or result is None or request.get('error'):
                continue
            if isinstance(result, dict) and result.get('job_id'):
                completed = any(r['tool'] == 'job_status' and r.get('result', {}).get('job_id') == result['job_id']
                                and r['result'].get('status') == 'done' for r in self.requests)
                if not completed:
                    continue
            returned.add(request['tool'])
        truth = self.task.get('truth')
        position = rank(candidates, truth['file'], truth['line']) if truth else None
        return {'task': self.task['id'], 'complete': self.finished,
                'time_to_root_cause_s': None, 'root_cause_censored': True,
                'correct_fix': False, 'claimed_fix': self.claimed, 'false_fix': self.claimed,
                'requires_inconclusive': True,
                'preserved_inconclusive': self.finished and not self.claimed,
                'defects': 0, 'detected': 0, 'false_rejections': 0,
                'candidate': None, 'transcript': copy.deepcopy(self.requests),
                'true_line_rank': position, 'candidates': candidates,
                'workflow_outcome': 'observed' if returned == set(WORKFLOW) else 'inconclusive',
                'workflow_steps_returned': len(returned), 'client_workflow_outcome': self.outcome,
                'evidence_timed_out': self.evidence_timed_out,
                'repair': 'NOT CLAIMED: no source patch or independent repair checker in this tool surface'}


def load_plan(path):
    raw = Path(path).read_bytes()
    task = json.loads(raw)
    if tuple(s['tool'] for s in task['steps']) != WORKFLOW:
        raise ValueError('expected the five-step evidence workflow')
    task.setdefault('id', 'evidence')
    return [task], hashlib.sha256(raw).hexdigest()


def evidence_report(scores, digest, model):
    body = report(scores, digest, model)
    body.update(track='native-tools', native_validation='NOT CLAIMED: evidence-only trial; no independent source repair check')
    return body


def run_evidence_trial(plan, command, out, *, budget_s=110, max_calls=32, model=None, repeats=1):
    from .external import run_trial
    tasks, _ = load_plan(plan)
    def loader(path):
        selected, digest = load_plan(path)
        selected[0]['budget_s'] = budget_s
        return selected, digest
    return run_trial(plan, tasks[0]['id'], command, out, budget_s=budget_s, max_calls=max_calls,
                     model=model, repeats=repeats, _load=loader, _session_factory=ToolSession,
                     _report=evidence_report,
                     _tool_surface='five native rvw evidence tools over MCP; no source patch or shell tool')
