"""Run selectors must not silently replace a requested revision with a source tree."""
import pytest

from rvw.regress.cli import execute_json
from rvw.regress.config import ConfigError, load_config
from rvw.regress.plan import source_for


@pytest.mark.parametrize('rev', ['HEAD', 'missing-revision'])
def test_source_for_rejects_conflicting_selectors(fake, rev):
    with pytest.raises(ConfigError, match='--source and --rev are mutually exclusive'):
        source_for(load_config(str(fake.config)), rev, fake.repo)


@pytest.mark.parametrize('transport', ['cli', 'api', 'mcp'])
@pytest.mark.parametrize('rev', ['HEAD', 'missing-revision'])
def test_run_rejects_conflicting_selectors_before_execution(fake, rvw, tmp_path, transport, rev):
    out = tmp_path / 'out'
    args = dict(core=str(fake.config), tier='quick', rev=rev, source=str(fake.repo), out=str(out))
    if transport == 'cli':
        code, _, data = rvw('regress', 'run', '--core', fake.config, '--tier', 'quick',
                            '--rev', rev, '--source', fake.repo, '--out', out, '--json')
        assert code == 2 and data is None
        assert 'mutually exclusive' in rvw.stderr
    elif transport == 'api':
        with pytest.raises(ValueError, match='mutually exclusive'):
            execute_json('run', **args)
    else:
        from rvw.mcp.registry import Registry
        registry, problems = Registry.discover({'regress'})
        assert not problems
        try:
            _, data, error = registry.call_json('regress_run', args)
            if not error and 'job_id' in data:
                _, data, error = registry.call_json('job_status', {'job_id': data['job_id'], 'wait_s': 60})
                assert not error and data['status'] == 'failed', data
            assert 'mutually exclusive' in str(data), data
        finally:
            registry.jobs.shutdown()
    assert not fake.calls()
    assert not out.exists()
