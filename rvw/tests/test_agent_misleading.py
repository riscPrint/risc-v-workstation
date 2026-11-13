"""Incomplete and misleading evidence must not earn a repair claim."""
from pathlib import Path

import pytest

from rvw.agent_bench.engine import Session, EXPRESSIONS, load_pack, report, scripted

pytestmark = pytest.mark.fast
PACK = Path(__file__).resolve().parents[2] / 'examples/agent-bench/misleading.json'


def test_scripted_client_rejects_all_five_evidence_defects_and_preserves_unknown():
    tasks, digest = load_pack(PACK)
    scores = []
    assert len(tasks) == 5
    for task in tasks:
        session = Session(task)
        registry = session.registry()
        try:
            scripted(registry.call)
            score = session.score()
            assert score['complete'] and score['preserved_inconclusive']
            assert not score['claimed_fix'] and not score['correct_fix']
            assert score['detected'] == 1 and score['false_rejections'] == 0
            assert score['root_cause_censored']
            scores.append(score)
        finally:
            registry.jobs.shutdown()
    summary = report(scores, digest, 'scripted')['summary']
    assert summary['inconclusive_required'] == summary['inconclusive_preserved'] == 5
    assert summary['false_fix_rate'] is None


def test_a_correct_expression_cannot_earn_a_fix_without_required_evidence():
    tasks, _ = load_pack(PACK)
    for task in tasks:
        session = Session(task)
        session.patch('s1', EXPRESSIONS['add'])
        session.finish(True)
        score = session.score()
        assert score['false_fix'] and not score['correct_fix']
        assert not score['preserved_inconclusive']


def test_careless_client_claims_false_fixes_on_all_incomplete_cases():
    tasks, digest = load_pack(PACK)
    scores = []
    for task in tasks:
        session = Session(task)
        registry = session.registry()
        try:
            scripted(registry.call, careless=True)
            scores.append(session.score())
        finally:
            registry.jobs.shutdown()
    summary = report(scores, digest, 'careless')['summary']
    assert summary['false_fixes'] == summary['claimed_fixes'] == 5
    assert summary['inconclusive_preserved'] == 0
    assert summary['detected'] == 0
