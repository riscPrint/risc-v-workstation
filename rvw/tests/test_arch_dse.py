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


def pareto_fixture(native_fixture, tmp_path):
    from rvw.arch import core
    rows = []
    for i, (area, power) in enumerate([(2, 1), (1, 2), (3, 3)]):
        out = tmp_path / f'model-{i}'
        core.run(native_fixture, 'fixture-0', out)
        report = out / 'gem5.json'
        data, benches, digest = core.checked_report(report)
        cycles = sum(b['cycles'] for b in benches.values())
        costs = tmp_path / f'costs-{i}.json'
        costs.write_text(json.dumps(dict(schema='rvw.arch-costs/1', report_sha256=digest,
            method='synthetic cost fixture, not measured hardware',
            cycles=[cycles * .9, cycles, cycles * 1.1],
            area_mm2=[area * .9, area, area * 1.1], power_w=[power * .9, power, power * 1.1])))
        rows.append(dict(id=str(i), report=str(report), costs=str(costs)))
    plan = tmp_path / 'pareto.json'
    plan.write_text(json.dumps(dict(schema='rvw.arch-pareto-plan/1', points=rows)))
    return plan, costs


def test_pareto_tradeoffs(native_fixture, tmp_path):
    plan, _ = pareto_fixture(native_fixture, tmp_path)
    result = dse.pareto(plan)
    assert result['nominal_frontier'] == ['0', '1']
    # Cycle uncertainty overlaps, so nominal cost dominance is not certain.
    assert result['conservative_frontier'] == ['0', '1', '2']
    assert all(p['evidence_class'] == 'model-only' for p in result['points'])


@pytest.mark.parametrize('field,value', [('power_w', None), ('cycles', None)])
def test_pareto_missing_objective(native_fixture, tmp_path, field, value):
    plan, costs = pareto_fixture(native_fixture, tmp_path)
    data = json.loads(costs.read_text()); data[field] = value
    costs.write_text(json.dumps(data))
    result = dse.pareto(plan)
    assert result['status'] == 'inconclusive'
    assert not result['points'][-1]['eligible']
    assert '2' not in result['conservative_frontier']


@pytest.mark.parametrize('field,value', [('report_sha256', 'wrong'), ('method', ''),
    ('area_mm2', [3, 2, 1]), ('power_w', [False, 1, 2]), ('cycles', [1, 2, 3])])
def test_pareto_invalid_costs(native_fixture, tmp_path, field, value):
    plan, costs = pareto_fixture(native_fixture, tmp_path)
    data = json.loads(costs.read_text()); data[field] = value
    costs.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        dse.pareto(plan)
