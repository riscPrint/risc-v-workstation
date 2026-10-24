"""Known-failure imports use the requested core for indexed and explicit sources."""
import pytest

from rvw.regress.store import append_index
from rvw.results import save_results
from test_regress_round19_core import _results


def call_known(transport, rvw, **args):
    if transport == 'cli':
        argv = ['regress', 'known', 'add', '--json']
        for key, value in args.items():
            argv += ['--' + key.rstrip('_').replace('_', '-'), str(value)]
        code, _, data = rvw(*argv)
        return code == 0, data if data is not None else rvw.stderr
    from rvw.mcp.registry import Registry
    registry, problems = Registry.discover({'regress'})
    assert not problems
    try:
        _, data, error = registry.call_json('regress_known_add', args)
        return not error, data
    finally:
        registry.jobs.shutdown()


@pytest.mark.parametrize('transport', ['cli', 'mcp'])
def test_known_latest_is_scoped_by_core(fake, rvw, tmp_path, transport):
    for name, signature in [('fake', 'fail:3'), ('other', 'fail:7')]:
        result = _results(name)
        result.tests[0].signature = signature
        path = tmp_path / name
        save_results(result, path)
        append_index({'core': name, 'run_id': name, 'path': str(path)})
    ok, data = call_known(transport, rvw, core=str(fake.config), from_='latest', reason='triaged')
    assert ok, data
    assert data['entries'][0]['signature'] == 'fail:3'


@pytest.mark.parametrize('transport', ['cli', 'mcp'])
@pytest.mark.parametrize('mixed', [False, True])
def test_known_explicit_path_refuses_wrong_core_before_writing(fake, rvw, tmp_path, transport, mixed):
    path = tmp_path / 'input'
    if mixed:
        save_results(_results('fake'), path / 'first')
    save_results(_results('other'), path / 'second')
    dest = tmp_path / 'known.toml'
    dest.write_text('# keep this file\n')
    ok, data = call_known(transport, rvw, core=str(fake.config), file=str(dest),
                          from_=str(path), reason='triaged')
    assert not ok, data
    assert 'core' in str(data)
    assert dest.read_text() == '# keep this file\n'
