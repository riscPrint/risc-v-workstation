"""Endpoint build failures cannot establish a historical regression."""
import pytest
from rvw.bisect.core import Bisector, Options


@pytest.mark.parametrize('skipped', ['bad?', 'good?'])
def test_skipped_endpoint_is_inconclusive(skipped):
    b = object.__new__(Bisector)
    b.o = Options(good='good')
    b.good, b.badrev, b.sig = 'good', 'bad', 'fail:1'
    def test(rev, label):
        return {'verdict': 'skip' if label == skipped else 'bad',
                'signature': 'no-result' if label == skipped else 'fail:1'}
    b.test = test
    b.g = lambda *args, **kw: ''
    b.save = lambda result: result
    result = b._bisect()
    assert result['inconclusive'] is True
    assert 'first_bad' not in result
    assert 'pick an older one' not in result['error']
