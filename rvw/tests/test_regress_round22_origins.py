"""Performance values require the same recorded measurement origin on every seed."""
import pytest

from rvw.regress.cli import execute_json
from rvw.regress.compare import compare
from rvw.results import find_results
from test_regress import T, _res
from test_regress_commit_gate import _mcp


def result(value=100, origin='cycles', name='cycles', seed=1):
    entry = T('q', cycles=value if name == 'cycles' else None, seed=seed,
              **({name: value} if name != 'cycles' else {}))
    if origin is not None:
        entry.extra['metric_origins'] = {name: origin}
    else:
        entry.extra.pop('metric_origins', None)
    return _res([entry], suite='bench', perf=[name + (':max' if name == 'ipc' else '')])


@pytest.mark.parametrize('transport', ['cli', 'mcp'])
def test_changed_cycles_definition_cannot_accept(fake, rvw, tmp_path, transport):
    config = fake.config.read_text().replace('[suites.isa]', '[suites.isa]\nperf_metrics = ["cycles"]')
    fake.config.write_text(config)
    for side, text, selector in [('base', 'cycles=100 roi_cycles=50', 'cycles'),
                                 ('candidate', 'cycles=200 roi_cycles=100', 'metrics.roi_cycles')]:
        rev = fake.commit({'rv64ui-p-add': text}, msg=side)
        fake.config.write_text(config.replace('[suites.isa]', f'[suites.isa]\ncycles_key = "{selector}"'))
        assert execute_json('run', core=str(fake.config), tier='quick', rev=rev,
                            out=str(tmp_path / side), no_cache=True, no_index=True)['ok']
        entry = find_results(tmp_path / side)[0].tests[0]
        assert entry.extra.get('metric_origins', {}).get('cycles') == selector
    if transport == 'cli':
        code, _, verdict = rvw('regress', 'compare', tmp_path / 'base', tmp_path / 'candidate', '--json')
        assert code == 3
    else:
        verdict = _mcp('compare', base=str(tmp_path / 'base'), candidate=str(tmp_path / 'candidate'))
    assert verdict['verdict'] == 'inconclusive'
    assert any('origin' in item['why'] for item in verdict['inconclusive'])
    assert not any(item['id'] == 'rv64ui-p-add' for item in verdict['perf'])


@pytest.mark.parametrize('origin', [None, 'metrics.roi_cycles'])
def test_missing_or_different_origin_is_inconclusive(origin):
    verdict = compare([result()], [result(origin=origin)])
    assert verdict.verdict == 'inconclusive' and not verdict.perf


def test_mixed_fallbacks_across_seeds_are_inconclusive():
    base, cand = result(), result()
    base.tests += result(seed=2, origin='metrics.roi_cycles').tests
    cand.tests += result(seed=2, origin='metrics.roi_cycles').tests
    assert compare([base], [cand]).verdict == 'inconclusive'


@pytest.mark.parametrize('value', [0, -1])
@pytest.mark.parametrize('side', ['base', 'candidate'])
def test_nonpositive_relative_metric_is_inconclusive(value, side):
    base, cand = result(), result()
    (base if side == 'base' else cand).tests[0].cycles = value
    verdict = compare([base], [cand])
    assert verdict.verdict == 'inconclusive' and not verdict.perf


def test_negative_custom_metric_cannot_reverse_relative_loss():
    verdict = compare([result(-100, 'metrics.cost', 'cost')], [result(-50, 'metrics.cost', 'cost')])
    assert verdict.verdict == 'inconclusive' and not verdict.perf


def test_custom_cycles_cannot_override_selected_cycles():
    base, cand = result(), result(200)
    base.tests[0].metrics['cycles'] = cand.tests[0].metrics['cycles'] = 1
    assert compare([base], [cand]).verdict == 'reject'


def test_derived_ipc_requires_equal_component_origins():
    origin = {'operation': 'instret/cycles', 'instret': 'instret', 'cycles': 'cycles'}
    base, cand = result(1, origin, 'ipc'), result(1, {**origin, 'instret': 'metrics.roi_instret'}, 'ipc')
    assert compare([base], [cand]).verdict == 'inconclusive'


def test_each_metric_uses_tolerance_before_display_rounding():
    base, cand = result(), result(101)
    base.extra['perf_metrics'].append('ipc:max')
    cand.extra['perf_metrics'].append('ipc:max')
    for res, ipc in [(base, 1.0), (cand, 0.979999)]:
        res.tests[0].metrics['ipc'] = ipc
        res.tests[0].extra['metric_origins']['ipc'] = 'metrics.ipc'
    verdict = compare([base], [cand], perf_tolerance=0.02)
    assert verdict.verdict == 'reject'
    assert {p['metric']: p['regression'] for p in verdict.perf} == {'cycles': False, 'ipc': True}


def test_runner_records_fallbacks_and_derived_ipc_without_rounding(fake, tmp_path):
    fake.prog('towers.riscv', 'cycles=123457 instret=1', bench=True)
    output = tmp_path / 'bench'
    assert execute_json('run', core=str(fake.config), suite='bench', out=str(output),
                        no_cache=True, no_index=True)['ok']
    entries = {t.id: t for t in find_results(output)[0].tests}
    assert entries['qsort'].extra['metric_origins']['cycles'] == 'metrics.roi_cycles'
    towers = entries['towers']
    assert towers.extra['metric_origins']['cycles'] == 'cycles'
    assert towers.extra['metric_origins']['ipc'] == {
        'operation': 'instret/cycles', 'instret': 'instret', 'cycles': 'cycles'}
    assert towers.metrics['ipc'] == 1 / 123457


def test_extra_candidate_seeds_cannot_hide_performance_regression():
    base, cand = result(), result(200)
    cand.tests += result(50, seed=2).tests + result(50, seed=3).tests
    verdict = compare([base], [cand])
    assert verdict.verdict == 'inconclusive' and not verdict.perf
