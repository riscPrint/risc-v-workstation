"""Address-trigger matrices check prefix effects and the matched access."""
import pytest
from rvw.debug import checks, profile, suite
from rvw.debug.triggers import TriggerUnit

pytestmark = pytest.mark.fast


def config(xlen=32, kind=2, matches=(0, 1, 2, 3)):
    return profile.normalize({'xlen': xlen, 'scratch': 0x80010000, 'modes': 'M',
        'triggers': {'count': 2, 'types': [kind], 'matches': list(matches),
                     'accesses': ['execute', 'load', 'store']}})


@pytest.mark.parametrize('access', ['load', 'store'])
def test_address_match_matrix(access):
    p = config()
    driver, _ = suite.model_driver(p)
    row = suite.run_one(suite.CHECKS['trig.' + access + '_address'], p, driver)
    assert row['status'] == 'pass', row
    assert row['observations'][access + '_matches'] == {'0': 8, '1': 16, '2': 12, '3': 0}


@pytest.mark.parametrize('access', ['load', 'store'])
def test_non_equality_match_bug_is_detected(monkeypatch, access):
    original = TriggerUnit._value_match
    def broken(self, slot, value):
        return original(self, slot, value) if self.field(slot, 'match') == 0 else False
    monkeypatch.setattr(TriggerUnit, '_value_match', broken)
    p = config()
    driver, _ = suite.model_driver(p)
    row = suite.run_one(suite.CHECKS['trig.' + access + '_address'], p, driver)
    assert row['status'] == 'fail', row
    assert access + ' match 1:' in row['message']


@pytest.mark.parametrize('access', ['load', 'store'])
@pytest.mark.parametrize('xlen', [32, 64])
@pytest.mark.parametrize('kind', [2, 6])
def test_masked_and_inverted_address_matches(access, xlen, kind):
    p = config(xlen, kind, (4, 5, 8, 9, 10, 11, 12, 13))
    driver, _ = suite.model_driver(p)
    row = suite.run_one(suite.CHECKS['trig.' + access + '_address'], p, driver)
    assert row['status'] == 'pass', row
    assert row['observations'][access + '_matches'] == {
        '4': 16, '5': 0, '8': 0, '9': 0, '10': 0, '11': 4, '12': 0, '13': 32}


@pytest.mark.parametrize('access', ['load', 'store'])
def test_empty_address_matches_cannot_pass(monkeypatch, access):
    monkeypatch.setattr(TriggerUnit, '_value_match', lambda *args: False)
    p = config(matches=())
    driver, _ = suite.model_driver(p)
    row = suite.run_one(suite.CHECKS['trig.' + access + '_address'], p, driver)
    assert row['status'] == 'fail', row
    assert 'no address matches' in row['message']
