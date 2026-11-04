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
