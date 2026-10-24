"""Stored performance evidence must cover the requested metric declarations."""
import pytest

from test_regress_round21_plan import gate, stored


@pytest.mark.parametrize('transport', ['cli', 'mcp'])
@pytest.mark.parametrize('change', ['add', 'remove', 'direction', 'key'])
def test_stored_metric_plan_must_match(fake, rvw, tmp_path, transport, change):
    original = fake.config.read_text()
    if change != 'add':
        fake.config.write_text(original.replace('[suites.isa]', '[suites.isa]\nperf_metrics = ["cycles"]'))
    output = stored(fake, tmp_path)
    requested = original
    if change != 'remove':
        direction = 'cycles:max' if change == 'direction' else 'cycles'
        requested = requested.replace('[suites.isa]', f'[suites.isa]\nperf_metrics = ["{direction}"]')
    if change == 'key':
        requested = requested.replace('[suites.isa]', '[suites.isa]\ncycles_key = "metrics.roi_cycles|cycles"')
    fake.config.write_text(requested)
    verdict = gate(fake, rvw, output, transport, tier='quick')
    assert verdict['verdict'] == 'inconclusive', verdict
    assert verdict['inconclusive_cause'] == 'stored_plan_incomplete'
    assert any('performance' in p['why'] for p in verdict['stored_plan_problems'])


def test_matching_stored_performance_plan_accepts(fake, rvw, tmp_path):
    fake.config.write_text(fake.config.read_text().replace('[suites.isa]', '[suites.isa]\nperf_metrics = ["cycles"]'))
    output = stored(fake, tmp_path)
    assert gate(fake, rvw, output, 'cli', tier='quick')['verdict'] == 'accept'
