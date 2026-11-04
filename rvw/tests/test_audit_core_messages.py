"""C3 publication must retain the evidence used to derive failure identity."""
import pytest

from rvw.regress.cli import execute_json


@pytest.mark.parametrize('status', ['assert', 'rvfi_error'])
def test_gate_rejects_failures_that_differ_after_message_preview(fake, status):
    prefix = 'x' * 450
    base = fake.commit({'rv64ui-p-add': f'status={status} message={prefix}left'}, 'first')
    cand = fake.commit({'rv64ui-p-add': f'status={status} message={prefix}right'}, 'second')
    verdict = execute_json('gate', core=str(fake.config), base_rev=base, cand_rev=cand,
                           no_cache=True)
    assert verdict['verdict'] == 'reject'
    assert verdict['new_failures']
    assert not verdict['still_failing']


def test_legacy_cut_message_cannot_cover_a_different_failure():
    from rvw.regress.compare import compare
    from rvw.results import failure_signature
    from test_regress import T, _res

    def saved(suffix):
        t = T('a', 'assert', failure_signature('assert', message='x' * 450 + suffix))
        t.extra['message'] = 'x' * 400  # Old Runner._entry preview, no full message retained.
        return _res([t])

    verdict = compare([saved('left')], [saved('right')])
    assert verdict.verdict == 'inconclusive'
    assert not verdict.extra['still_failing']


@pytest.mark.parametrize('complete,expected', [(True, 'accept'), (False, 'inconclusive')])
def test_message_completeness_marker_controls_exact_limit(complete, expected):
    from rvw.regress.compare import compare
    from rvw.results import failure_signature
    from test_regress import T, _res

    t = T('a', 'assert', failure_signature('assert', message='x' * 400))
    t.extra.update(message='x' * 400, message_complete=complete)
    assert compare([_res([t])], [_res([t])]).verdict == expected
