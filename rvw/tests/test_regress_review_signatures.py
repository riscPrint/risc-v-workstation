"""Negative cases for saved and generated failure identities (#2)."""
import pytest

from rvw.regress.compare import compare
from rvw.regress.known import Known
from rvw.results import failure_signature
from test_regress import T, _res


@pytest.mark.parametrize('left,right', [
    ('bad register 0x1000', 'bad register 0x2000'),
    ('monitor failed\nregister mismatch', 'monitor failed\nmemory mismatch'),
    ('x' * 200 + 'left', 'x' * 200 + 'right'),
])
def test_uncoded_rvfi_errors_keep_full_identity(left, right):
    assert failure_signature('rvfi_error', message=left) != failure_signature('rvfi_error', message=right)


def test_saved_rvfi_message_overrides_legacy_lossy_signature():
    b, c = T('a', 'rvfi_error', 'rvfi_error:bad register 0x*'), T('a', 'rvfi_error', 'rvfi_error:bad register 0x*')
    b.extra['message'], c.extra['message'] = 'bad register 0x1000', 'bad register 0x2000'
    assert compare([_res([b])], [_res([c])]).verdict == 'reject'


def test_saved_fail_code_overrides_stale_signature_and_waiver():
    b, c = T('a', 'fail', 'fail:3'), T('a', 'fail', 'fail:3')
    b.extra['fail_code'], c.extra['fail_code'] = 3, 7
    verdict = compare([_res([b])], [_res([c])], [Known('isa', 'a', 'fail:3')])
    assert verdict.verdict == 'reject'
    assert verdict.new_failures[0]['signature'] == 'fail:7'


def test_equal_signature_cannot_cover_a_changed_status():
    b, c = T('a', 'fail', 'timeout'), T('a', 'timeout', 'timeout')
    assert compare([_res([b])], [_res([c])]).verdict != 'accept'


def test_legacy_uncoded_rvfi_without_message_needs_rerun():
    t = T('a', 'rvfi_error', 'rvfi_error:bad register 0x*')
    verdict = compare([_res([t])], [_res([t])], [Known('isa', 'a', 'rvfi_error:*')])
    assert verdict.verdict == 'inconclusive'
    assert not verdict.known_failures


@pytest.mark.parametrize('signature,config', [('fail:*', 'small'), ('fail:?', 'small'),
    ('fail:[37]', 'small'), ('fail:3', None)])
@pytest.mark.parametrize('baseline_failed', [False, True])
def test_broad_waiver_cannot_earn_accept(signature, config, baseline_failed):
    b = T('a', 'fail', 'fail:3') if baseline_failed else T('a')
    c = T('a', 'fail', 'fail:3')
    v = compare([_res([b])], [_res([c])], [Known('isa', 'a', signature, config=config)])
    assert v.verdict == 'inconclusive'
    assert not v.known_failures
    assert any('waiver' in i['why'] for i in v.inconclusive)


@pytest.mark.parametrize('status,signature,left,right', [
    ('fail', 'fail:3', 'register check failed', 'memory check failed'),
    ('timeout', 'timeout', 'waiting for load', 'waiting for branch'),
    ('rvfi_error', 'rvfi_error:105', 'monitor error 105: register', 'monitor error 105: memory'),
    ('assert', 'assert:lsu.scala:1241', 'lsu.scala:1241 load', 'lsu.scala:1241 store'),
])
def test_coarse_unchanged_signature_cannot_hide_changed_message(status, signature, left, right):
    b, c = T('a', status, signature), T('a', status, signature)
    b.extra.update(message=left, message_complete=True)
    c.extra.update(message=right, message_complete=True)
    assert compare([_res([b])], [_res([c])]).verdict == 'reject'
    # An exact waiver deliberately covers the declared diagnostic class.
    v = compare([_res([b])], [_res([c])], [Known('isa', 'a', signature, config='small')])
    assert v.verdict == 'accept'
    assert v.known_failures
