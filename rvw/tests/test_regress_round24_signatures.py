"""Assertion identities must distinguish new failures, including old C3 results."""
import pytest

from rvw.regress.cli import execute_json
from rvw.results import failure_signature


def test_hdl_assertions_keep_their_line_numbers():
    message = "[0] %Error: /tmp/build/core.sv:{}: Assertion failed in core: 'assert' failed."
    assert failure_signature('assert', message=message.format(4)) == 'assert:core.sv:4'
    assert failure_signature('assert', message=message.format(6)) == 'assert:core.sv:6'


@pytest.mark.parametrize('left,right', [
    ('Assertion failed at pc 0x80001000', 'Assertion failed at pc 0x80002000'),
    ('Assertion failed\nleft condition', 'Assertion failed\nright condition'),
    ('x' * 200 + 'left', 'x' * 200 + 'right'),
    ('java.lang.IllegalStateException: seed=1234', 'java.lang.IllegalStateException: seed=5678'),
])
def test_unlocated_assertions_bind_the_full_message(left, right):
    assert failure_signature('assert', message=left) != failure_signature('assert', message=right)
    assert failure_signature('assert', message=left) == failure_signature('assert', message=left)


def test_changed_hdl_assertion_rejects_committed_gate(fake):
    base = fake.commit({'rv64ui-p-add': 'status=assert message=core.sv:4:_Assertion_failed'}, 'first')
    cand = fake.commit({'rv64ui-p-add': 'status=assert message=core.sv:6:_Assertion_failed'}, 'second')
    verdict = execute_json('gate', core=str(fake.config), base_rev=base, cand_rev=cand,
                           no_cache=True)
    assert verdict['verdict'] == 'reject'
    assert verdict['new_failures'][0]['signature'] == 'assert:core.sv:6'
    assert not verdict['still_failing']


def test_compare_rederives_legacy_assertions_from_saved_full_messages():
    from test_regress import T, _res
    from rvw.regress.compare import compare

    old = "assert:core.sv: Assertion failed"
    base = _res([T('a', 'assert', old)])
    cand = _res([T('a', 'assert', old)])
    base.tests[0].extra['message'] = 'core.sv:4: Assertion failed'
    cand.tests[0].extra['message'] = 'core.sv:6: Assertion failed'
    verdict = compare([base], [cand])
    assert verdict.verdict == 'reject'
    assert not verdict.extra['still_failing']


def test_unlocated_legacy_assertions_without_messages_cannot_cover_each_other():
    from test_regress import T, _res
    from rvw.regress.compare import compare

    verdict = compare([_res([T('a', 'assert', 'assert:condition')])],
                      [_res([T('a', 'assert', 'assert:condition')])])
    assert verdict.verdict == 'inconclusive'
    assert not verdict.extra['still_failing']
