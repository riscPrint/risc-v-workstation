"""Cooperative reservation fixtures. No OS resource limit is claimed."""
import json

import pytest

from rvw.farm.resources import reserve


@pytest.fixture
def capacity(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path))
    config = tmp_path / '.config/rvw'
    config.mkdir(parents=True)
    (config / 'farm-capacity.json').write_text(json.dumps(dict(
        cpu=4, memory_bytes=100, disk_bytes=1000, jobs=3,
        projects={'a': dict(cpu=2, memory_bytes=50, disk_bytes=600, jobs=1),
                  'b': dict(cpu=3, memory_bytes=80, disk_bytes=800, jobs=2)})))
    return tmp_path / 'state'


@pytest.mark.parametrize('dimension,value', [('cpu', 2), ('memory_bytes', 30), ('disk_bytes', 400), ('jobs', 1)])
def test_project_queue_and_other_project_progress(capacity, dimension, value):
    request = dict(project='a', cpu=1, memory_bytes=30, disk_bytes=400, jobs=1)
    with reserve(request, .05, capacity) as first:
        assert first['limits']['disk_bytes'] == 600
        with pytest.raises(ValueError, match='wait timeout'):
            with reserve(dict(project='a', **{dimension: value}), .01, capacity):
                pytest.fail('project capacity exceeded')
        with reserve(dict(project='b', cpu=1, memory_bytes=20, disk_bytes=100), .05, capacity):
            pass
    assert first['released'] and first['outcome'] == 'completed' and first['held_s'] > 0
    assert json.loads((capacity / 'reservations.json').read_text()) == []


@pytest.mark.parametrize('resources', [dict(project='a', disk_bytes=601), dict(project='a', jobs=2),
                                      dict(project='unknown'), dict(), dict(project='a', disk_bytes=-1),
                                      dict(project='a', jobs=True), dict(project='a', typo=1)])
def test_refuse_invalid_or_oversized(capacity, resources):
    with pytest.raises(ValueError):
        with reserve(resources, .01, capacity):
            pytest.fail('invalid reservation admitted')


def test_cancel_releases_all_dimensions(capacity):
    report = None
    with pytest.raises(KeyboardInterrupt):
        with reserve(dict(project='a', disk_bytes=600), .05, capacity) as report:
            raise KeyboardInterrupt()
    assert report['released'] and report['outcome'] == 'cancelled_or_error'
    with reserve(dict(project='a', disk_bytes=600), .05, capacity):
        pass


@pytest.mark.parametrize('timeout', [float('nan'), float('inf'), 0, -1, True])
def test_refuse_unbounded_wait(capacity, timeout):
    with pytest.raises(ValueError):
        with reserve(dict(project='a'), timeout, capacity):
            pytest.fail('invalid wait admitted')


def test_existing_reservations_count_as_one_job(capacity):
    config = capacity.parent / '.config/rvw/farm-capacity.json'
    data = json.loads(config.read_text())
    data['jobs'] = 1
    config.write_text(json.dumps(data))
    capacity.mkdir()
    (capacity / 'reservations.json').write_text(json.dumps([
        dict(token='old-worker', pid=123, cpu=1, memory_bytes=0, locks=[])]))
    with pytest.raises(ValueError, match='wait timeout'):
        with reserve(dict(project='a'), .01, capacity):
            pytest.fail('existing worker was not counted')
