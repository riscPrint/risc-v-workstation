import json
import pytest
from rvw.farm.classify import classify


def report(tmp_path, campaign, status, *, seed=1, inconclusive=None, missing=False):
    path = tmp_path / f'{campaign}.json'
    path.write_text(json.dumps({'schema': 'rvw.farm/1', 'campaign_id': campaign,
        'identity': {'tools': 'native-fixture'},
        'plan': [{'id': '0', 'options': {'config': 'a', 'seed': seed}, 'elf_sha256': 'a'*64}],
        'shards': [{'cells': [] if missing else [{'id': '0', 'status': status, 'inconclusive': inconclusive}]}]}))
    return path


def test_later_pass_does_not_erase_failure(tmp_path):
    paths = [report(tmp_path, 'first', 'fail'), report(tmp_path, 'second', 'pass')]
    group = classify(paths)['groups'][0]
    assert group['status'] == 'fail'
    assert group['unstable']
    assert group['observed_dut_failure']
    assert [a['outcome']['status'] for a in group['attempts']] == ['fail', 'pass']
    assert all(a['report_sha256'] and a['campaign_id'] for a in group['attempts'])


def test_infrastructure_fault_is_not_dut_flakiness(tmp_path):
    paths = [report(tmp_path, 'first', 'fail', inconclusive='worker died'), report(tmp_path, 'second', 'pass')]
    group = classify(paths)['groups'][0]
    assert group['status'] == 'inconclusive'
    assert group['infrastructure_fault']
    assert not group['unstable']
    assert not group['observed_dut_failure']


def test_missing_attempt_stays_incomplete(tmp_path):
    group = classify([report(tmp_path, 'first', 'pass', missing=True), report(tmp_path, 'second', 'pass')])['groups'][0]
    assert group['status'] == 'inconclusive'
    assert group['attempts'][0]['category'] == 'missing'


def test_different_seeds_are_separate_groups(tmp_path):
    result = classify([report(tmp_path, 'first', 'fail'), report(tmp_path, 'second', 'pass', seed=2)])
    assert len(result['groups']) == 2
    assert not any(g['unstable'] for g in result['groups'])


def test_duplicate_execution_is_refused(tmp_path):
    path = report(tmp_path, 'first', 'pass')
    with pytest.raises(ValueError, match='duplicate campaign'):
        classify([path, path])


def test_old_uncaptured_report_is_refused(tmp_path):
    path = tmp_path / 'old.json'; path.write_text('{"schema":"rvw.farm/1"}')
    with pytest.raises(ValueError, match='identities'):
        classify([path])


@pytest.mark.parametrize('status', ['assert', 'rvfi_error'])
def test_checker_failure_survives_later_pass(tmp_path, status):
    group = classify([report(tmp_path, 'first', status),
                      report(tmp_path, 'second', 'pass')])['groups'][0]
    assert group['status'] == 'fail'
    assert group['unstable']
