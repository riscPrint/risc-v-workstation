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


@pytest.fixture
def native_mapping(tmp_path):
    stats = ('---------- Begin Simulation Statistics ----------\n'
        'simFreq 1000000000000\nsimTicks 100000\nfinalTick 200000\n'
        'system.mem.bytesRead 800\nsystem.mem.reads 4\nsystem.mem.latency 80000\n'
        '---------- End Simulation Statistics ----------\n'
        '---------- Begin Simulation Statistics ----------\n'
        'system.mem.bytesRead 99999\n---------- End Simulation Statistics ----------\n')
    values = dict(stats=stats, config=json.dumps(dict(path='system', mem=dict(path='system.mem'))),
        bare=json.dumps(dict(tohost=1, exit_code=0, roi='setStats',
            bench_stats=dict(cycles=100, instret=20), roi_ticks=[100000, 200000])))
    inputs = {}
    for key, value in values.items():
        source = tmp_path / (key + '.txt'); source.write_text(value)
        inputs[key] = dict(path=str(source), sha256=digest(source.read_bytes()))
    counters = dict(bytes=dict(stats=['system.mem.bytesRead'], scale=1),
                    transactions=dict(stats=['system.mem.reads'], scale=1),
                    latency_ns_sum=dict(stats=['system.mem.latency'], scale=.001))
    data = dict(schema='rvw.memory-mapping/1', inputs=inputs, observations=[dict(
        point='system.mem', region='setStats', hart='0', workload='fixture', counters=counters)])
    path = tmp_path / 'mapping.json'; path.write_text(json.dumps(data))
    return path, data


def test_extract_first_marker_bound_dump(native_mapping):
    from rvw.arch.memory import memory_extract
    path, data = native_mapping
    report = memory_extract(path)
    assert report['observations'][0]['metrics']['bandwidth_GB_s'] == 8
    assert report['observations'][0]['metrics']['mean_latency_ns'] == 20
    assert report['observations'][0]['metrics']['mean_outstanding'] is None
    assert report['native_inputs']['stats']['sha256'] == data['inputs']['stats']['sha256']


@pytest.mark.parametrize('change', ['hash', 'point', 'counter', 'scale', 'roi', 'missing', 'duplicate'])
def test_extract_refuses_unbound_counters(native_mapping, change):
    from pathlib import Path
    from rvw.arch.memory import memory_extract
    path, data = native_mapping
    row = data['observations'][0]
    if change == 'hash':
        data['inputs']['stats']['sha256'] = 'bad'
    elif change == 'point':
        row['point'] = 'system.wrong'
    elif change == 'counter':
        row['counters']['bytes']['stats'] = ['system.other.bytes']
    elif change == 'scale':
        row['counters']['bytes']['scale'] = False
    else:
        source = Path(data['inputs']['stats']['path'])
        text = source.read_text()
        if change == 'roi':
            text = text.replace('simTicks 100000', 'simTicks 99999')
        elif change == 'missing':
            text = text.replace('system.mem.reads 4', 'system.mem.other 4')
        else:
            text = text.replace('simFreq 1000000000000', 'simFreq 1000000000000\nsimFreq 1000000000000')
        source.write_text(text)
        data['inputs']['stats']['sha256'] = digest(source.read_bytes())
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        memory_extract(path)
