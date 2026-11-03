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
    assert metric['comparison_rule'] == 'relative_mean'


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
