"""Metric directions and selectors have closed, checked syntax."""
import pytest

from rvw.regress.compare import compare
from rvw.regress.config import ConfigError, Suite, load_config
from test_regress import T, _res


def result():
    return _res([T('q', cycles=100)], suite='bench', perf=['cycles'])


BAD_SPECS = [['ipc:mx'], ['cycles:'], [':max'], ['cycles:min:extra'], [' cycles'],
             ['cycles', 'cycles:max'], ['cycles', 'cycles'], [7], 'cycles']


@pytest.mark.parametrize('specs', BAD_SPECS)
def test_suite_rejects_invalid_metric_specs(specs):
    with pytest.raises(ConfigError, match='performance metric'):
        Suite('bench', perf_metrics=specs)


@pytest.mark.parametrize('specs', BAD_SPECS)
def test_compare_rejects_invalid_stored_metric_specs(specs):
    base, cand = result(), result()
    cand.extra['perf_metrics'] = specs
    with pytest.raises(ValueError, match='performance metric'):
        compare([base], [cand])


@pytest.mark.parametrize('specs', ['["ipc:mx"]', '["cycles", "cycles:max"]'])
def test_config_load_checks_directions(fake, specs):
    fake.config.write_text(fake.config.read_text().replace('perf_metrics = ["cycles"]', 'perf_metrics = ' + specs))
    with pytest.raises(ConfigError, match='performance metric'):
        load_config(str(fake.config))


@pytest.mark.parametrize('suffix', ['', ':min', ':lower', ':max', ':higher'])
def test_documented_directions_remain_valid(suffix):
    base, cand = result(), result()
    base.extra['perf_metrics'] = cand.extra['perf_metrics'] = ['cycles' + suffix]
    assert compare([base], [cand]).verdict == 'accept'


@pytest.mark.parametrize('key', ['cycles_key', 'instret_key'])
@pytest.mark.parametrize('selector', ['', 'cycles|', '|cycles', 'metrics..cycles', 'metrics.cycles||cycles', 7])
def test_suite_rejects_malformed_selectors(key, selector):
    with pytest.raises(ConfigError, match=key):
        Suite('bench', **{key: selector})


@pytest.mark.parametrize('transport', ['cli', 'mcp'])
@pytest.mark.parametrize('action', ['config', 'compare'])
def test_invalid_directions_error_through_both_transports(fake, rvw, tmp_path, transport, action):
    from rvw.mcp.registry import Registry
    from rvw.results import save_results
    if action == 'config':
        fake.config.write_text(fake.config.read_text().replace('perf_metrics = ["cycles"]', 'perf_metrics = ["ipc:mx"]'))
        arguments = {'core': str(fake.config)}
        tool = 'list'
    else:
        base, cand = result(), result()
        base.extra['perf_metrics'] = cand.extra['perf_metrics'] = ['ipc:mx']
        save_results(base, tmp_path / 'base')
        save_results(cand, tmp_path / 'cand')
        arguments = {'base': str(tmp_path / 'base'), 'candidate': str(tmp_path / 'cand')}
        tool = 'compare'
    if transport == 'cli':
        args = (['--core', fake.config] if action == 'config' else [tmp_path / 'base', tmp_path / 'cand'])
        code, _, _ = rvw('regress', tool, *args, '--json')
        assert code == 2 and 'performance metric' in rvw.stderr
    else:
        registry, problems = Registry.discover({'regress'})
        assert not problems
        try:
            _, data, error = registry.call_json('regress_' + tool, arguments)
            assert error and 'performance metric' in str(data), data
        finally:
            registry.jobs.shutdown()
    assert not fake.calls()
    assert not (tmp_path / 'cand' / 'verdict.json').exists()
