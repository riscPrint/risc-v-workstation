import json
from rvw.workloads import core
from rvw.workloads.mcp_tools import execute_json, mcp_tools
from rvw.cli import main


def test_riscv_recipe_selection(capsys):
    assert main(['workloads', 'list', '--recipe', 'riscv-tests']) == 0
    data = json.loads(capsys.readouterr().out)
    assert {'median', 'dhrystone', 'spmv'} <= {w['id'] for w in data['workloads']}
    assert len(data['revision']) == 40
    assert len(data['dependencies']['env']) == 40
    assert data['runtime_files']
    assert execute_json('list', recipe='riscv-tests') == data
    assert {t.name for t in mcp_tools()} == {'workloads_list', 'workloads_build', 'workloads_verify'}


def test_open_recipe_pins_and_checkers():
    for name, workload in [('coremark', 'coremark-smoke'), ('zstd', 'zstd-roundtrip')]:
        data = core.load(core.recipe(name))
        assert len(data['revision']) == 40
        assert data['workloads'][0]['id'] == workload
        assert data['workloads'][0]['stdout_sha256'] == core.EMPTY
        assert data['workloads'][0]['expected']


def test_capture_dependency_revision(tmp_path):
    import subprocess
    source = tmp_path / 'source'
    source.mkdir()
    subprocess.run(['git', 'init', '-q', str(source)], check=True)
    subprocess.run(['git', '-C', str(source), 'config', 'user.name', 'Test'], check=True)
    subprocess.run(['git', '-C', str(source), 'config', 'user.email', 'test@example.com'], check=True)
    (source / 'encoding.h').write_text('pinned header')
    subprocess.run(['git', '-C', str(source), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(source), 'commit', '-qm', 'fixture'], check=True)
    revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    (source / 'encoding.h').write_text('dirty header')
    destination = tmp_path / 'captured'
    core.archive_source(source, revision, destination)
    assert (destination / 'encoding.h').read_text() == 'pinned header'


def test_omitted_public_source_resolves_pin(tmp_path, monkeypatch):
    import pytest
    calls = []
    def acquire(name, *, acquire, revision):
        assert acquire is True
        calls.append((name, revision))
        raise RuntimeError('acquisition fixture')
    monkeypatch.setattr('rvw.common.dependencies.resolve', acquire)
    with pytest.raises(RuntimeError, match='acquisition fixture'):
        core.build(core.recipe('riscv-tests'), out=tmp_path / 'out')
    assert calls == [('riscv-tests', core.load(core.recipe('riscv-tests'))['revision'])]
    assert not (tmp_path / 'out').exists()


def test_local_licensed_source_still_required(tmp_path, monkeypatch):
    import pytest
    data = core.load(core.recipe('riscv-tests'))
    del data['revision']
    data['source_sha256'] = 'a' * 64
    manifest = tmp_path / 'licensed.json'
    manifest.write_text(json.dumps(data))
    monkeypatch.setattr('rvw.regress.source.ensure_pinned_source', lambda *a, **kw: pytest.fail('licensed download'))
    with pytest.raises(ValueError, match='explicit local source'):
        core.build(manifest, out=tmp_path / 'out')


def test_workload_cli_and_mcp_accept_omitted_source(tmp_path, monkeypatch, capsys):
    import pytest
    def fail(*args, **kw):
        raise RuntimeError('resolver fixture')
    monkeypatch.setattr(core, 'build', fail)
    assert main(['workloads', 'build', '--recipe', 'riscv-tests', '--out', str(tmp_path)]) == 2
    assert json.loads(capsys.readouterr().out)['error'] == 'resolver fixture'
    with pytest.raises(RuntimeError, match='resolver fixture'):
        execute_json('build', recipe='riscv-tests', out=str(tmp_path))
