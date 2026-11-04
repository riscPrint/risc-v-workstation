"""Required performance evidence cannot disappear through classification (#4)."""
import pytest
from rvw.regress.compare import compare
from rvw.regress.known import Known
from test_regress import T, _res


def test_added_required_perf_workload_needs_a_baseline():
    base = _res([T('smoke')])
    cand = _res([T('smoke')])
    bench = _res([T('bench', cycles=100)], suite='bench', perf=['cycles'])
    verdict = compare([base], [cand, bench])
    assert verdict.verdict == 'inconclusive'
    assert any('baseline' in i['why'] for i in verdict.inconclusive)


@pytest.mark.parametrize('waived', [False, True])
def test_failed_perf_workload_cannot_silently_skip_required_metrics(waived):
    b = _res([T('bench', 'fail', 'fail:3', cycles=100)], perf=['cycles'])
    c = _res([T('bench', 'fail', 'fail:3', cycles=200)], perf=['cycles'])
    known = [Known('isa', 'bench', 'fail:3')] if waived else []
    verdict = compare([b], [c], known)
    assert verdict.verdict == 'inconclusive'
    assert any('performance' in i['why'] for i in verdict.inconclusive)


def test_repeated_seed_report_states_counts_and_confidence_limit():
    def samples(values):
        return _res([T('bench', seed=i, cycles=v) for i, v in enumerate(values, 1)], perf=['cycles'])
    verdict = compare([samples([100, 110, 120])], [samples([101, 111, 121])])
    assert verdict.verdict == 'accept'
    metric = verdict.perf[0]
    assert metric['samples'] == {'base': 3, 'candidate': 3, 'paired': 3}
    assert metric['confidence'] == 'not_estimated'
    assert metric['comparison_rule'] == 'max_paired_relative_loss'


def test_stored_failed_metric_workload_does_not_earn_accept(fake, rvw, tmp_path):
    from rvw.regress.cli import execute_json
    from test_regress_round21_plan import gate

    fake.config.write_text(fake.config.read_text().replace(
        '[suites.isa]', '[suites.isa]\nperf_metrics = ["cycles"]'))
    fake.commit({'rv64ui-p-add': 'status=fail fail_code=3 cycles=100'}, 'failed workload')
    output = tmp_path / 'stored'
    assert not execute_json('run', core=str(fake.config), tier='quick', out=str(output),
                            no_cache=True, no_index=True)['ok']
    verdict = gate(fake, rvw, output, 'cli', tier='quick', allow_missing=True)
    assert verdict['verdict'] == 'inconclusive'
    assert verdict['still_failing']
    assert any('performance' in i['why'] for i in verdict['inconclusive'])


@pytest.mark.parametrize('direction,base,candidate', [
    ('cycles', [100, 100], [130, 70]),
    ('ipc:max', [1.0, 1.0], [0.7, 1.3]),
])
def test_fast_seed_cannot_cancel_slow_seed(direction, base, candidate):
    name = direction.split(':')[0]
    def samples(values):
        return _res([T('bench', seed=i, **{name: v}) for i, v in enumerate(values, 1)], perf=[direction])
    v = compare([samples(base)], [samples(candidate)], perf_tolerance=0.01)
    assert v.verdict == 'reject'
    assert v.perf[0]['regression']
    assert v.perf[0]['comparison_rule'] == 'max_paired_relative_loss'
    assert v.perf[0]['worst_seed'] == 1
    assert v.perf[0]['max_paired_loss'] == pytest.approx(0.3)


@pytest.mark.parametrize('direction,base,candidate', [('cycles', 100, 125), ('ipc:max', 4, 3)])
def test_paired_loss_threshold_equality_does_not_reject(direction, base, candidate):
    name = direction.split(':')[0]
    b = _res([T('bench', **{name: base})], perf=[direction])
    c = _res([T('bench', **{name: candidate})], perf=[direction])
    assert compare([b], [c], perf_tolerance=0.25).verdict == 'accept'
    assert compare([b], [c], perf_tolerance=0.24).verdict == 'reject'
