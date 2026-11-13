import json
import sys
from pathlib import Path
from rvw.results import Verdict
from rvw.farm.service import Queue
from rvw.farm.verdict_costs import costs_by_verdict


def test_costs_link_original_c4_without_inventing_verdict(tmp_path):
    q = Queue(tmp_path)
    job = q.submit('agent', [sys.executable, '-c', 'pass'])
    done = q.work_once()
    folder = Path(done['attempts'][0]['directory'])
    report = costs_by_verdict(q, 'agent:agent')
    assert report['by_recorded_verdict']['not_recorded']['attempts'] == 1
    verdict = folder / 'verdict.json'
    verdict.write_text(json.dumps(Verdict('reject').to_dict()))
    before = verdict.read_bytes()
    report = costs_by_verdict(q, 'agent:agent')
    assert report['by_recorded_verdict']['reject']['attempts'] == 1
    assert report['verdict_attempts'][0]['verdict_links'][0]['sha256']
    assert verdict.read_bytes() == before
    verdict.write_text('{}')
    assert 'ambiguous' in costs_by_verdict(q, 'agent:agent')['by_recorded_verdict']


def test_exhausted_priority_owner_does_not_block_other_work(tmp_path):
    from rvw.farm.costs import configure, report
    q = Queue(tmp_path)
    configure(q, 'agent:a', dict(jobs=1))
    q.submit('a', [sys.executable, '-c', 'pass'])
    q.work_once()
    exhausted = q.submit('a', ['true'], priority=10)
    other = q.submit('b', [sys.executable, '-c', 'pass'])
    assert q.work_once()['id'] == other['id']
    assert next(j for j in q.jobs() if j['id'] == exhausted['id'])['state'] == 'budget_exhausted'
    assert 'by_recorded_verdict' in report(q, 'agent:b')


def test_equal_priority_gives_less_served_owner_a_turn(tmp_path):
    q = Queue(tmp_path)
    for _ in range(3):
        q.submit('a', [sys.executable, '-c', 'pass'])
    assert q.work_once()['owner'] == 'a'
    q.submit('b', [sys.executable, '-c', 'pass'])
    assert q.work_once()['owner'] == 'b'
