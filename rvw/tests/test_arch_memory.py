"""Memory report arithmetic and evidence checks, using synthetic observations."""
import json
import pytest
from rvw.arch.core import digest
from rvw.arch.memory import memory_report


@pytest.fixture
def observation(tmp_path):
    evidence = tmp_path / 'raw.txt'
    evidence.write_text('synthetic interval counters')
    row = dict(point='memory.port', region='bandwidth', hart='0', workload='fixture',
               duration_ns=100, bytes=800, transactions=4, latency_ns_sum=80,
               cache_accesses=10, cache_misses=2, outstanding_ns=200, queue_full_ns=25,
               evidence='raw.txt', evidence_sha256=digest(evidence.read_bytes()),
               mapping='fixture fields use ns, bytes and transaction counts')
    path = tmp_path / 'observations.json'
    return path, row


def report(path, row):
    path.write_text(json.dumps(dict(schema='rvw.memory-observations/1', engine='gem5', observations=[row])))
    return memory_report(path)


def test_metrics(observation):
    path, row = observation
    result = report(path, row)['observations'][0]
    assert result['metrics'] == dict(bandwidth_GB_s=8, mean_latency_ns=20, miss_rate=.2,
                                   mean_outstanding=2, queue_full_fraction=.25)
    assert result['contention_cause'] == 'unobserved'


def test_missing_is_not_zero(observation):
    path, row = observation
    del row['bytes']
    row['transactions'] = 0
    result = report(path, row)['observations'][0]
    assert result['metrics']['bandwidth_GB_s'] is None
    assert result['metrics']['mean_latency_ns'] is None


@pytest.mark.parametrize('key,value', [('duration_ns', 0), ('bytes', -1), ('hart', ''),
    ('cache_misses', 11), ('queue_full_ns', 101), ('evidence_sha256', 'bad'), ('mapping', '')])
def test_invalid_observations(observation, key, value):
    path, row = observation
    row[key] = value
    with pytest.raises(ValueError):
        report(path, row)


def test_cli(observation, rvw):
    path, row = observation
    report(path, row)
    code, _, result = rvw('arch', 'memory-report', path, '--json')
    assert code == 0 and result['status'] == 'reported'
