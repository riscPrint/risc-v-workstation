import json
from rvw.farm.notifications import notifications


def test_events_keep_dut_and_infrastructure_separate(tmp_path):
    report = {'schema': 'rvw.farm/1', 'campaign_id': 'fixture', 'expected_cells': 3,
        'status': 'inconclusive', 'shards': [{'host': 'a', 'status': 'inconclusive',
            'cells': [{'id': '0', 'status': 'fail', 'inconclusive': None},
                      {'id': '1', 'status': 'error', 'inconclusive': 'worker'}],
            'missing_cells': ['2']}]}
    path = tmp_path / 'farm.json'; path.write_text(json.dumps(report))
    before = path.read_bytes()
    result = notifications(tmp_path)
    assert result['delivery'] == 'not_attempted'
    assert [e['kind'] for e in result['events']] == [
        'dut_failure', 'infrastructure_fault', 'incomplete_shard', 'collection_inconclusive']
    assert notifications(tmp_path) == result
    assert path.read_bytes() == before


def test_complete_collection_with_failure_does_not_notify_pass(tmp_path):
    (tmp_path / 'farm.json').write_text(json.dumps({'campaign_id': 'fixture', 'expected_cells': 1,
        'status': 'complete', 'shards': [{'host': 'a', 'status': 'complete',
            'cells': [{'id': '0', 'status': 'fail', 'inconclusive': None}]}]}))
    kinds = [e['kind'] for e in notifications(tmp_path)['events']]
    assert kinds == ['dut_failure', 'collection_complete']


def test_checker_failures_emit_dut_notifications(tmp_path):
    (tmp_path / 'farm.json').write_text(json.dumps({'campaign_id': 'fixture', 'expected_cells': 2,
        'status': 'complete', 'shards': [{'host': 'a', 'status': 'complete',
            'cells': [{'id': str(i), 'status': status, 'inconclusive': None}
                      for i, status in enumerate(['assert', 'rvfi_error'])]}]}))
    assert [e['kind'] for e in notifications(tmp_path)['events']] == [
        'dut_failure', 'dut_failure', 'collection_complete']
