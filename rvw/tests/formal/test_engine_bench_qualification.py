import pytest
from rvw.formal import engine_bench

pytestmark = pytest.mark.fast


def test_conditional_native_pass_does_not_count_as_solved(tmp_path, monkeypatch):
    def race(plan, *args, **kwargs):
        conditional = plan['id'] == 'conditional'
        return {'status': 'inconclusive' if conditional else 'pass',
                'rows': [{'engine': 'abc:pdr', 'status': 'pass', 'wall_s': 0.01}],
                'environment_check': 'activation_not_checked' if conditional else 'no_source_assumptions',
                'source_sha256': [], 'mode': 'prove', 'depth': 20}
    monkeypatch.setattr(engine_bench, 'race', race)
    report = engine_bench.benchmark({'engines': ['abc:pdr'], 'cases': [{'id': 'conditional'}, {'id': 'closed'}]},
                                    tmp_path, tmp_path / 'out', 1)
    summary = report['summary']['abc:pdr']
    assert summary['solved'] == 1 and summary['conditional_passes'] == 1
    conditional = report['rows'][0]
    assert conditional['status'] == 'pass' and conditional['problem_status'] == 'inconclusive'
