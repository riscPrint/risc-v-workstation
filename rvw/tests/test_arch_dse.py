"""Small synthetic sweeps. No native model accuracy claims."""
import json
import sqlite3
import pytest
from test_arch_model import description
from test_arch import native_fixture
from rvw.arch import dse


def spec():
    return dict(schema='rvw.arch-sweep/1', parameters={'cpu.fetchWidth': [2, 4]},
                max_points=2, timeout_s=10)


def test_sorted_reproducible_points(description):
    a = dse.points(description, spec())
    assert [p['cpu']['fetchWidth'] for p in a] == [2, 4]
    assert description['cpu']['fetchWidth'] == 2
    assert dse.canonical(a) == dse.canonical(dse.points(description, spec()))


@pytest.mark.parametrize('change', [dict(max_points=1), dict(timeout_s=0),
    dict(parameters={'cpu.fetchWidth': [2, 2]}), dict(parameters={'cpu.unknown': [1]}),
    dict(parameters={'cpu.fetchWidth': [True]}), dict(parameters={'config': ['other']})])
def test_bad_plan(description, change):
    plan = {**spec(), **change}
    with pytest.raises(ValueError):
        dse.points(description, plan)


def test_sweep_database_and_failures(native_fixture, tmp_path, monkeypatch):
    path = tmp_path / 'sweep.json'
    # Fixture description contains a scalar CPU fetchWidth.
    # Use the project parser to find the fixture's actual description.
    from rvw.arch import core
    _, _, base = core.settings(native_fixture)
    key = next(k for k, v in base['cpu'].items() if type(v) is int)
    original = base['cpu'][key]
    plan = spec()
    plan['parameters'] = {'cpu.' + key: [original, original + 1]}
    path.write_text(json.dumps(plan))
    out = tmp_path / 'dse'
    result = dse.sweep(path, out, native_fixture, 'fixture-0')
    assert len(result['points']) == 2
    assert result['status'] == 'reported'
    assert len(result['pareto']) == 2  # fixture has identical counters
    with sqlite3.connect(out / 'results.sqlite') as db:
        assert db.execute('SELECT count(*) FROM points').fetchone()[0] == 2
    first = result['points'][0]['id']
    other = dse.sweep(path, tmp_path / 'other', native_fixture, 'fixture-0')
    assert other['points'][0]['id'] == first
    monkeypatch.setattr(core, 'run_models', lambda *a, **kw: (_ for _ in ()).throw(ValueError('failed fixture')))
    failed = dse.sweep(path, tmp_path / 'failed', native_fixture, 'fixture-0')
    assert failed['status'] == 'inconclusive' and failed['pareto'] == []
    assert all(p['cycles'] is None for p in failed['points'])
