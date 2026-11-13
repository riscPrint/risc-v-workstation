"""Counter conversion must distinguish missing samples from measured zero."""
import pytest
from rvw.probes import api
from test_probes import probe, stream

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('target', ['counts', 'hpm'])
def test_missing_counter_total_is_not_zero(tmp_path, target):
    events = stream(tmp_path, [probe(0, 'counter', 'misses', ['inc'], hpm='4')], [])
    with pytest.raises(ValueError, match='misses.*total'):
        api.run_convert(events, target, tmp_path / 'out', c1=events, c2=events)


@pytest.mark.parametrize('target', ['counts', 'hpm'])
def test_explicit_zero_counter_total_is_preserved(tmp_path, target):
    events = stream(tmp_path, [probe(0, 'counter', 'misses', ['inc'], hpm='4')], [], counters={'misses': 0})
    result = api.run_convert(events, target, tmp_path / 'out', c1=events, c2=events)
    assert result['counts'] == {'misses': 0} if target == 'counts' else result['bindings'] == 1
