"""Synthetic processes and VexRiscv description checks, not native RTL evidence."""
import json
from pathlib import Path
import os
import time

import pytest
from test_arch import native_fixture, reports, read_json, write_json
from test_arch_fitting import plan
from rvw.arch import core
from rvw.arch.fitting import fit
from rvw.arch.ledger import predict, score_prediction
from rvw.arch.measure import measure
from rvw.arch.search import search, propose
from rvw.arch.statistics import interval, correlation


def test_statistics():
    assert interval([1])['status'] == 'inconclusive'
    assert interval([2, 2])['ci95'] == [2, 2]
    assert interval([1, 2, 3])['ci95'][0] <= 2 <= interval([1, 2, 3])['ci95'][1]
    assert correlation([(1, 2), (2, 4), (3, 6)])['pearson_r'] == 1
    assert correlation([(1, 3)] * 3)['status'] == 'inconclusive'
    assert correlation([(1, 2)])['pearson_r'] is None


def test_correlations_split(plan):
    result = fit(plan)
    assert result['event_correlations']['held_out']['branches']['status'] == 'inconclusive'


def test_bayesian_acquisition():
    vectors = [[0], [.5], [1]]
    assert propose(vectors, {}) == 0
    assert propose(vectors, {0: 1, 1: 0}) == 2
    assert propose(vectors, {0: 1}) in (1, 2)


def test_prediction_later_scoring(reports, tmp_path, rvw):
    rtl, model = reports
    record = tmp_path / 'prediction.json'
    assert rvw('arch', 'predict', model, '--out', record, '--json')[0] == 0
    with pytest.raises(ValueError, match='after'):
        score_prediction(record, rtl, tmp_path / 'too-early.json')
    future = time.time() + 1
    for row in read_json(rtl)['benchmarks']:
        os.utime(row['evidence'], (future, future))
    scored = tmp_path / 'score.json'
    assert rvw('arch', 'score-prediction', record, rtl, '--out', scored, '--json')[0] == 0
    assert read_json(scored)['comparison']['status'] == 'reported'
    with pytest.raises(FileExistsError): predict(model, record)
    data = read_json(record)
    data['prediction']['core'] = 'changed'
    write_json(record, data)
    with pytest.raises(ValueError, match='changed'):
        score_prediction(record, rtl, tmp_path / 'tampered.json')


def test_measure_both_engines(native_fixture, rvw):
    out = native_fixture.parent / 'repeated'
    code, _, result = rvw('--project', native_fixture, 'arch', 'measure', '--bench',
                          'fixture-0,fixture-1', '--out', out, '--repeats', '2', '--json')
    assert code == 0, result
    assert result['benchmarks'][0]['ipc_ratio']['ci95'] == [2, 2]
    assert len(result['reports']) == 2
    assert len((native_fixture.parent / 'calls.jsonl').read_text().splitlines()) == 8


@pytest.fixture(params=['synthetic', 'vexriscv-description'])
def search_plan(native_fixture, tmp_path, request):
    if request.param == 'vexriscv-description':
        root = Path(__file__).resolve().parents[2]
        description = read_json(root / 'examples/vexriscv/rvw/arch/minor.json')
        write_json(tmp_path / 'description.json', description)
        native_fixture.write_text(native_fixture.read_text().replace('fixture-o3', 'rv32im').replace('arch-fixture', 'vexriscv'))
        adapter = tmp_path / 'fake-c1-adapter.py'
        adapter.write_text(adapter.read_text().replace('arch-fixture', 'vexriscv'))
    core.calibrate(native_fixture, 'fixture-0,fixture-1', tmp_path / 'baseline', 30)
    # The fixture emits explicit ROI stats, with parameter-dependent training error.
    gem5 = tmp_path / 'fake-native-gem5'
    source = gem5.read_text()
    source += '''
settings = json.loads(description.read_text())
value = settings['bus_bytes']
(out / 'stats.txt').write_text('---------- Begin Simulation Statistics ----------\\n'
                              + 'system.cpu.cycles ' + str(value * 25 if index == 0 else value * 100) + '\\n'
                              + '---------- End Simulation Statistics   ----------\\n')
'''
    gem5.write_text(source)
    spec = {'schema': 'rvw.arch-search/1', 'parameters': {'bus_bytes': [4, 8, 16]},
            'budget': 2, 'repeats': 2, 'timeout_s': 30,
            'fit': {'schema': 'rvw.arch-fit-plan/1', 'rtl': str(tmp_path / 'baseline/rtl.json'),
                    'candidates': {}, 'train': ['fixture-0'], 'held_out': ['fixture-1'],
                    'events': [{'name': 'cycles', 'rtl_metric': 'roi_cycles', 'gem5_stat': 'system.cpu.cycles',
                                'unit': 'cycles', 'semantics': 'Synthetic ROI fixture.'}],
                    'scope': 'Synthetic target.', 'uncertainty': 'No native measurement.', 'unsupported': []}}
    path = tmp_path / 'search-plan.json'
    write_json(path, spec)
    return path, native_fixture


def test_search_serial_training_then_held_out(search_plan, rvw):
    plan_path, project = search_plan
    out = plan_path.parent / 'search'
    code, _, result = rvw('--project', project, 'arch', 'search', plan_path, '--out', out, '--json')
    assert code == 0, result
    assert len(result['trials']) == 2
    best = min(result['trials'], key=lambda t: t['training']['mean'])
    assert result['selected'] == best['point']
    assert result['held_out']['n'] == 2
    calls = [json.loads(line) for line in (plan_path.parent / 'calls.jsonl').read_text().splitlines()]
    calls = [c for c in calls[4:] if c['engine'] == 'gem5']
    assert [Path(c['args'][4]).stem for c in calls] == ['fixture-0'] * 4 + ['fixture-1'] * 2
    assert len(result['reports']) == 2


@pytest.mark.parametrize('mutation', ['overlap', 'alias', 'budget', 'repeats', 'latency'])
def test_search_rejects_before_model(search_plan, mutation):
    plan_path, project = search_plan
    spec = read_json(plan_path)
    if mutation == 'overlap': spec['fit']['held_out'] = spec['fit']['train']
    if mutation == 'alias': spec['fit']['held_out'] = ['missing']
    if mutation == 'budget': spec['budget'] = 100
    if mutation == 'repeats': spec['repeats'] = True
    if mutation == 'latency': spec['parameters'] = {'memory_latency': [20, 21]}
    write_json(plan_path, spec)
    before = (plan_path.parent / 'calls.jsonl').read_bytes()
    with pytest.raises(ValueError): search(plan_path, plan_path.parent / 'bad', project)
    assert (plan_path.parent / 'calls.jsonl').read_bytes() == before


def test_vexriscv_parameter_space():
    from rvw.arch.dse import points
    root = Path(__file__).resolve().parents[2]
    description = read_json(root / 'examples/vexriscv/rvw/arch/minor.json')
    candidates = points(description, {'schema': 'rvw.arch-sweep/1', 'parameters': {'bus_bytes': [4, 8]},
                                      'max_points': 2, 'timeout_s': 30})
    assert all(c['kind'] == 'minor' and c['isa'] == 'rv32im' for c in candidates)


def test_mcp_search(search_plan):
    from rvw.mcp.registry import Registry
    from test_arch import mcp_finished
    plan_path, project = search_plan
    registry, problems = Registry.discover({'arch'})
    assert not problems
    assert {'arch_search', 'arch_measure', 'arch_predict', 'arch_score_prediction'} <= registry.tools.keys()
    try:
        result = mcp_finished(registry, 'arch_search', {'plan': str(plan_path),
                              'project': str(project), 'out': str(plan_path.parent / 'mcp-search')})
        assert result['status'] == 'done', result
        assert result['result']['held_out']['n'] == 2
    finally:
        registry.jobs.shutdown(grace=.2)


def test_measure_rejects_changed_inputs(native_fixture, monkeypatch):
    original = core.calibrate
    def changing(*args):
        report = original(*args)
        description = native_fixture.parent / 'description.json'
        data = read_json(description)
        data['bus_bytes'] *= 2
        write_json(description, data)
        return report
    monkeypatch.setattr(core, 'calibrate', changing)
    out = native_fixture.parent / 'changed-measurement'
    with pytest.raises(ValueError, match='changed'):
        measure(out, native_fixture, 'fixture-0,fixture-1', 30, 2)
    assert not (out / 'measure.json').exists()
