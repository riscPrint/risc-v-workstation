import pytest
from rvw.probes.check import check
from rvw.init.mapped import PROBE_TEMPLATE
pytestmark = pytest.mark.fast


def test_names_missing_fetch_flush_and_stall(monkeypatch):
    monkeypatch.setattr('rvw.probes.api.report', lambda **kw: dict(source={},probes=[dict(kind='flush',name='decode')]))
    r = check(events='unused', require=['flush/fetch','flush/decode','stall'])
    assert r['status']=='inconclusive' and r['missing_probes']==['flush/fetch','stall']
    assert check(events='unused',require=['flush/decode'])['status']=='present'


def test_template_flushes_both_younger_slots_and_measures_stalls():
    assert 'redirect && fetchValid, fetchId' in PROBE_TEMPLATE
    assert 'redirect && decodeValid, decodeId' in PROBE_TEMPLATE
    assert '"fetch_wait", fetchStall' in PROBE_TEMPLATE
    assert '"data_wait", dataStall' in PROBE_TEMPLATE
