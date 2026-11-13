"""Layer ownership and weakest-input verdicts. No native evidence is produced."""
import json
import sys
import pytest
from rvw.common.verdicts import producer_verdict, weakest_verdict
from rvw.evidence.index import build, query
from rvw.farm.service import Queue
from rvw.farm.workflows import workflow
from rvw.plan import VPlan

pytestmark = pytest.mark.fast
BLOCKERS = ['inconclusive', 'unsupported', 'not_installed']


def write(path, data):
    path.write_text(json.dumps(data))
    return path


def plan(tmp_path, role, ref):
    return write(tmp_path/'plan.json', dict(schema='rvw.vplan/1', requirements={'r': 'Declared requirement.'},
        features=[dict(id='f', requirements=['r'], **{role: [ref]})]))


@pytest.mark.parametrize('blocker', BLOCKERS + ['fail', 'error', 'no_checks'])
def test_any_blocker_prevents_pass_in_both_orders(blocker):
    assert weakest_verdict(['pass', blocker]) == blocker
    assert weakest_verdict([blocker, 'pass']) == blocker


def test_empty_unknown_and_completion_inputs_do_not_pass():
    assert weakest_verdict([]) == 'no_checks'
    assert weakest_verdict(['done']) == 'inconclusive'
    assert weakest_verdict(['pass', 'unknown']) == 'inconclusive'
    assert weakest_verdict(['pass', 'pass']) == 'pass'
    assert producer_verdict(dict(status='pass', verdict='unsupported')) == 'unsupported'
    assert producer_verdict(dict(status='pass', inconclusive='unattributed')) == 'inconclusive'
    assert producer_verdict(dict(status='complete')) == 'inconclusive'


@pytest.mark.parametrize('blocker', BLOCKERS)
def test_complete_coverage_counts_do_not_override_a_producer_blocker(tmp_path, blocker):
    write(tmp_path/'coverage.json', dict(schema='rvw.functional-coverage/1', status=blocker,
        config_sha256='a'*64, groups={'g': dict(fields=['v'], expected_bins=1, expected_hit=1, holes=[])}))
    result = VPlan(plan(tmp_path, 'coverage', dict(path='coverage.json', groups=['g']))).status()
    assert result['verdict'] == blocker
    assert result['features'][0]['verdict'] == blocker
    assert result['summary']['reported_closed'] == 0


@pytest.mark.parametrize('blocker', BLOCKERS)
def test_selected_c3_child_verdict_is_retained(tmp_path, blocker):
    write(tmp_path/'suite.json', dict(schema='rvw.results/1', run_id='fixture', suite='fixture', core='fixture',
        config='fixture', created='fixture', tests=[dict(id='t', status='pass', verdict=blocker)]))
    result = VPlan(plan(tmp_path, 'tests', dict(path='suite.json', ids=['t']))).status()
    assert result['verdict'] == blocker
    assert result['summary']['reported_closed'] == 0


@pytest.mark.parametrize('blocker', BLOCKERS)
def test_formal_child_cannot_be_strengthened_by_summary(tmp_path, blocker):
    write(tmp_path/'formal.json', dict(schema='rvw.formal-app-results/1', properties=[dict(
        property_id='p', status='pass', proof_kind='unbounded', result='child.json')]))
    write(tmp_path/'child.json', dict(schema='rvw.formal/1', status='pass', verdict=blocker,
        proof_kind='unbounded', assertions=1, reachability={'status': 'reachable'}))
    result = VPlan(plan(tmp_path, 'formal', dict(path='formal.json', properties=['p']))).status()
    assert result['verdict'] == blocker
    assert result['summary']['reported_closed'] == 0


def test_inconclusive_c1_failure_does_not_become_a_conclusive_failure(tmp_path):
    write(tmp_path/'run.json', dict(schema='rvw.run/1', status='fail', inconclusive='missing observation'))
    result = VPlan(plan(tmp_path, 'tests', dict(path='run.json'))).status()
    assert result['verdict'] == 'inconclusive'


@pytest.mark.parametrize('blocker', BLOCKERS)
def test_index_keeps_producer_status_and_owns_no_verification_verdict(tmp_path, blocker):
    write(tmp_path/'report.json', dict(schema='rvw.formal/1', status=blocker))
    db = tmp_path/'index.sqlite'
    build(tmp_path, db)
    result = query(db)
    assert result['verdict'] == 'not_inferred'
    assert result['matches'][0]['recorded_status'] == blocker
    assert result['matches'][0]['integrity'] == 'unchanged'


def test_farm_completion_without_evidence_does_not_pass(tmp_path):
    record = workflow(tmp_path, 'create', dict(nodes=[dict(id='n', command=[sys.executable, '-c', 'pass'])]))
    workflow(tmp_path, 'advance', workflow_id=record['id'])
    Queue(tmp_path).work_once()
    result = workflow(tmp_path, workflow_id=record['id'])
    assert result['state'] == 'complete'
    assert result['verification'] == 'not_inferred'
    assert result['verdict'] == 'inconclusive'


def test_guide_returns_advice_without_a_verification_pass():
    from rvw.mcp.registry import Registry
    registry, problems = Registry.discover({'agent'})
    assert not problems
    _, data, error = registry.call_json('agent_guide', {'workflow': 'bring-up'})
    assert not error and data['schema'] == 'rvw.agent-guide/1'
    assert data.get('verdict') not in ('pass', 'proven', 'match', 'accept')
