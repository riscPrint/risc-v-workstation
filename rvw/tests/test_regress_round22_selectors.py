"""Gate folder and revision selectors must never silently replace each other."""
import pytest

from rvw.regress.cli import execute_json
from rvw.regress.config import ConfigError, load_config
from rvw.regress.plan import gate
from rvw.regress.runner import RunOptions


@pytest.mark.parametrize('side', ['base', 'cand'])
def test_conflicting_selectors_fail_before_reading_or_running(fake, tmp_path, side):
    options = {side: str(tmp_path / 'missing'), side + '_rev': 'HEAD', 'base_rev': 'HEAD'}
    with pytest.raises(ValueError, match='mutually exclusive'):
        execute_json('gate', core=str(fake.config), **options)
    assert not fake.calls()
    assert not (tmp_path / 'results').exists()


@pytest.mark.parametrize('side', ['base', 'cand'])
def test_cli_conflicting_selectors_exit_two(fake, rvw, tmp_path, side):
    code, _, data = rvw('regress', 'gate', '--core', fake.config, '--base-rev', 'HEAD',
                       '--' + side, tmp_path / 'missing', *(['--cand-rev', 'HEAD'] if side == 'cand' else []), '--json')
    assert code == 2 and data is None
    assert 'mutually exclusive' in rvw.stderr
    assert not fake.calls()


@pytest.mark.parametrize('side', ['base', 'candidate'])
def test_python_gate_checks_selectors_before_resolving_folders(fake, tmp_path, side):
    with pytest.raises(ConfigError, match='mutually exclusive'):
        gate(load_config(str(fake.config)), 'quick', 'HEAD', 'HEAD',
             str(tmp_path / 'missing') if side == 'base' else None,
             str(tmp_path / 'missing') if side == 'candidate' else None,
             None, RunOptions(log=None), None, None)
    assert not fake.calls()


@pytest.mark.parametrize('side', ['base', 'cand'])
def test_mcp_conflicting_selectors_report_usage_error(fake, tmp_path, side):
    from rvw.mcp.registry import Registry
    registry, problems = Registry.discover({'regress'})
    assert not problems
    try:
        args = {'core': str(fake.config), 'base_rev': 'HEAD',
                side: str(tmp_path / 'missing'), side + '_rev': 'HEAD'}
        _, data, error = registry.call_json('regress_gate', args)
        if not error and 'job_id' in data:
            _, state, error = registry.call_json('job_status', {'job_id': data['job_id'], 'wait_s': 60})
            assert not error, state
            assert state['status'] == 'failed', state
            data = state
        assert 'mutually exclusive' in str(data), data
        assert not fake.calls()
    finally:
        registry.jobs.shutdown()
