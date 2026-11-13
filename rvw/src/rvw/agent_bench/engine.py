"""Evaluator state. Hidden fields never cross the tool boundary."""
from __future__ import annotations

import copy
import hashlib
import json
import time
import statistics
from pathlib import Path

from rvw.mcp.registry import Registry
from rvw.mcp.spec import ToolError, ToolSpec, schema

EXPRESSIONS = json.loads(Path(__file__).with_name('expressions.json').read_text())


def evaluate(expression: str, a: int, b: int) -> int:
    """Interpret a fixed Spinal expression subset, without executing agent code."""
    if expression not in {*EXPRESSIONS.values(), 'U(0, 32 bits)'}:
        raise ValueError('unsupported fixture expression')
    op = next((k for k, v in EXPRESSIONS.items() if v == expression), 'zero')
    sign = lambda x: x - (1 << 32) if x & (1 << 31) else x
    # Expected values are stored vectors, not calls to this implementation.
    functions = {
        'add': lambda: a + b, 'sub': lambda: a - b,
        'and': lambda: a & b, 'or': lambda: a | b, 'xor': lambda: a ^ b,
        'sll': lambda: a << (b & 31), 'srl': lambda: a >> (b & 31),
        'sltu': lambda: int(a < b), 'slt': lambda: int(sign(a) < sign(b)),
        'eq': lambda: int(a == b), 'zero': lambda: 0,
    }
    return functions[op]() & 0xffffffff


def load_pack(path: Path) -> tuple[list[dict], str]:
    raw = path.read_bytes()
    pack = json.loads(raw)
    if pack['schema'] != 'rvw.agent-tasks/1' or not pack['tasks']:
        raise ValueError('invalid task pack')
    tasks = pack['tasks']
    if len({t['id'] for t in tasks}) != len(tasks):
        raise ValueError('duplicate task ID')
    for t in tasks:
        p, truth = t['public'], t['private']
        if not set(p['expressions']) <= {*EXPRESSIONS.values(), 'U(0, 32 bits)'}:
            raise ValueError('unsupported task grammar')
        if not truth['vectors'] or truth['cause'] not in {s['id'] for s in p['statements']}:
            raise ValueError('missing evaluator checks or cause')
        original = next(s['source'].removeprefix('io.result := ') for s in p['statements'] if s['id'] == truth['cause'])
        if all(evaluate(original, a, b) == expected for a, b, expected in truth['vectors']):
            raise ValueError('seeded mutation does not fail')
    return tasks, hashlib.sha256(raw).hexdigest()


class Session:
    def __init__(self, task: dict, clock=time.monotonic, max_calls: int = 32):
        self.task = copy.deepcopy(task)
        self.clock, self.max_calls = clock, max_calls
        self.started = clock()
        self.events: list[dict] = []
        self.finished = False
        self.candidate = None
        self.claimed = False

    def _record(self, tool: str, arguments: dict):
        if self.finished:
            raise ToolError('session is finished')
        if len(self.events) >= self.max_calls:
            raise ToolError('tool budget exhausted')
        self.events.append({'tool': tool, 'arguments': copy.deepcopy(arguments),
                            'elapsed_s': self.clock() - self.started})

    def inspect(self):
        self._record('bench_inspect', {})
        return copy.deepcopy(self.task['public'])

    def diagnose(self, statement: str, evidence: list[str]):
        self._record('bench_diagnose', {'statement': statement, 'evidence': evidence})
        return {'recorded': True}  # Never expose whether a cause is correct.

    def reject(self, artifact: str, reason: str):
        self._record('bench_reject', {'artifact': artifact, 'reason': reason})
        return {'recorded': True}

    def patch(self, statement: str, expression: str):
        if expression not in self.task['public']['expressions']:
            raise ToolError('expression is outside the fixture grammar')
        if statement not in {s['id'] for s in self.task['public']['statements']}:
            raise ToolError('unknown statement')
        self._record('bench_patch', {'statement': statement, 'expression': expression})
        self.candidate = {'statement': statement, 'expression': expression}
        return {'recorded': True}

    def finish(self, claimed_fix: bool):
        self._record('bench_finish', {'claimed_fix': claimed_fix})
        self.claimed = claimed_fix
        self.finished = True
        return {'recorded': True}

    def score(self):
        truth = self.task['private']
        valid = {e['id'] for e in self.task['public']['evidence'] if e['id'] not in truth['defects']}
        cause = next((e['elapsed_s'] for e in self.events if e['tool'] == 'bench_diagnose'
                      and e['arguments']['statement'] == truth['cause']
                      and e['arguments']['evidence']
                      and set(e['arguments']['evidence']) <= valid), None)
        needs_inconclusive = truth.get('requires_inconclusive', False)
        correct = bool(not needs_inconclusive and self.finished and self.candidate
                       and self.candidate['statement'] == truth['cause']
                       and all(evaluate(self.candidate['expression'], a, b) == expected
                               for a, b, expected in truth['vectors']))
        rejections = {(e['arguments']['artifact'], e['arguments']['reason'])
                      for e in self.events if e['tool'] == 'bench_reject'}
        actual = set(truth['defects'].items())
        return {'task': self.task['id'], 'complete': self.finished,
                'time_to_root_cause_s': cause, 'root_cause_censored': cause is None,
                'correct_fix': correct, 'claimed_fix': self.claimed,
                'false_fix': self.claimed and not correct,
                'requires_inconclusive': needs_inconclusive,
                'preserved_inconclusive': bool(needs_inconclusive and self.finished and not self.claimed),
                'defects': len(actual), 'detected': len(rejections & actual),
                'false_rejections': len(rejections - actual),
                'candidate': self.candidate, 'transcript': copy.deepcopy(self.events)}

    def registry(self):
        string = {'type': 'string'}
        return Registry([
            ToolSpec('bench_inspect', 'Read the task and its evidence identities.', schema({}), self.inspect),
            ToolSpec('bench_diagnose', 'Record a cause and supporting artifact IDs.',
                     schema({'statement': string, 'evidence': {'type': 'array', 'items': string, 'minItems': 1}}, ['statement', 'evidence']), self.diagnose),
            ToolSpec('bench_reject', 'Reject an artifact with the mismatched identity field.',
                     schema({'artifact': string, 'reason': {'type': 'string', 'enum': ['rtl_sha256', 'elf_sha256', 'unsupported_fields', 'coverage', 'completion']}}, ['artifact', 'reason']), self.reject),
            ToolSpec('bench_patch', 'Replace one statement expression in the fixture.',
                     schema({'statement': string, 'expression': string}, ['statement', 'expression']), self.patch),
            ToolSpec('bench_finish', 'Finish without access to hidden test results.',
                     schema({'claimed_fix': {'type': 'boolean'}}, ['claimed_fix']), self.finish),
        ])


def scripted(call, careless=False):
    """Agent input is only a callable tool client, never evaluator state."""
    task = call('bench_inspect', {})
    valid = []
    for e in task['evidence']:
        mismatches = [k for k, v in task['identity'].items() if e['identity'].get(k) != v]
        if e.get('unsupported_fields'):
            mismatches.append('unsupported_fields')
        if e.get('coverage', {}).get('observed', 0) < e.get('coverage', {}).get('required', 0):
            mismatches.append('coverage')
        if e.get('complete') is False:
            mismatches.append('completion')
        if mismatches and not careless:
            for reason in mismatches:
                call('bench_reject', {'artifact': e['id'], 'reason': reason})
        else:
            valid.append(e['id'])
    if not valid and not careless:
        call('bench_finish', {'claimed_fix': False})
        return
    statement = next(s['id'] for s in task['statements'] if s['source'].startswith('io.result := '))
    call('bench_diagnose', {'statement': statement, 'evidence': valid})
    expression = 'U(0, 32 bits)' if careless else EXPRESSIONS[task['requirement']]
    call('bench_patch', {'statement': statement, 'expression': expression})
    call('bench_finish', {'claimed_fix': True})


def report(scores, digest, agent):
    n = len(scores)
    claimed = sum(s['claimed_fix'] for s in scores)
    defects = sum(s['defects'] for s in scores)
    times = [s['time_to_root_cause_s'] for s in scores if s['time_to_root_cause_s'] is not None]
    return {'schema': 'rvw.agent-bench/1', 'track': 'fixture', 'agent': agent,
            'task_pack_sha256': digest, 'tasks': scores,
            'summary': {'tasks': n, 'claimed_fixes': claimed,
                        'root_causes': len(times), 'censored_root_causes': n - len(times),
                        'median_time_to_root_cause_s': statistics.median(times) if times else None,
                        'correct_fixes': sum(s['correct_fix'] for s in scores),
                        'inconclusive_required': sum(s.get('requires_inconclusive', False) for s in scores),
                        'inconclusive_preserved': sum(s.get('preserved_inconclusive', False) for s in scores),
                        'correct_fix_rate': sum(s['correct_fix'] for s in scores) / n,
                        'false_fixes': sum(s['false_fix'] for s in scores),
                        'false_fix_rate': sum(s['false_fix'] for s in scores) / claimed if claimed else None,
                        'misleading_evidence': defects,
                        'detected': sum(s['detected'] for s in scores),
                        'misleading_evidence_recall': sum(s['detected'] for s in scores) / defects if defects else None,
                        'false_rejections': sum(s['false_rejections'] for s in scores)},
            'native_validation': 'NOT RUN'}
