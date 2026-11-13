import hashlib
import json
from datetime import date
import pytest
from rvw.common.waivers import validate_review, stale_state
from rvw.checks.qualification import summarize
from test_checks_qualification import inputs

pytestmark = pytest.mark.fast


def policy(tmp_path, inventory, **changes):
    entry = dict(id='one', disposition='waived', owner='core-owner', reason='Reviewed source mismatch', expires='2099-12-31')
    entry.update(changes)
    path = tmp_path/'dispositions.json'
    path.write_text(json.dumps(dict(schema='rvw.check-dispositions/1',
        inventory_sha256=hashlib.sha256(inventory.read_bytes()).hexdigest(), entries=[entry])))
    return path


def test_review_retains_raw_failure_counts_and_cli_failure(tmp_path):
    inventory, run = inputs(tmp_path, [dict(id='one', kind='csr.state', count=3)])
    dispositions = policy(tmp_path, inventory)
    result = summarize(inventory, [run], dispositions=dispositions)
    assert result['status'] == 'findings'
    assert result['runs'][0]['status'] == 'fail'
    assert result['counts']['csr.state']['firing_count'] == 3
    assert result['dispositions'][0]['matched'] is True
    assert result['disposition_status'] == 'reviewed_findings'
    from rvw.cli import main
    assert main(['checks', 'report', '--inventory', str(inventory), '--run', str(run),
        '--dispositions', str(dispositions), '--out', str(tmp_path/'summary.json')]) == 1


def test_missing_execution_is_unknown_but_observed_absence_is_stale(tmp_path):
    inventory, run = inputs(tmp_path)
    dispositions = policy(tmp_path, inventory)
    assert summarize(inventory, dispositions=dispositions)['dispositions'][0]['stale'] is None
    with pytest.raises(ValueError, match='stale disposition'):
        summarize(inventory, [run], dispositions=dispositions)
    inventory.write_text(inventory.read_text()+'\n')
    with pytest.raises(ValueError, match='inventory hash changed'):
        summarize(inventory, dispositions=dispositions)


@pytest.mark.parametrize('changes', [dict(owner=''), dict(reason=''), dict(expires='2020-01-01'),
                                      dict(expires='20990101'), dict(id='missing')])
def test_invalid_policy_is_an_error(tmp_path, changes):
    inventory, _ = inputs(tmp_path)
    with pytest.raises(ValueError):
        summarize(inventory, dispositions=policy(tmp_path, inventory, **changes))


def test_expiry_uses_utc_last_valid_day_and_unknown_is_not_stale():
    entry = dict(reason='reviewed', owner='owner', expires='2026-11-13')
    validate_review(entry, date(2026, 11, 13))
    with pytest.raises(ValueError, match='expired'):
        validate_review(entry, date(2026, 11, 14))
    assert stale_state(0, False) is None
    assert stale_state(0, True) is True
    assert stale_state(1, True) is False


def test_needs_review_does_not_mark_findings_as_reviewed(tmp_path):
    inventory, run = inputs(tmp_path, [dict(id='one', kind='csr.state', count=1)])
    result = summarize(inventory, [run], dispositions=policy(tmp_path, inventory, disposition='needs_review'))
    assert result['disposition_status'] == 'open_findings'
