"""Pinned acquisitions must remain usable after their original checkout is removed."""
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

import pytest
from rvw.regress import source

pytestmark = pytest.mark.fast


def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], text=True).strip()


@pytest.fixture
def upstream(tmp_path, monkeypatch):
    repo = tmp_path / 'upstream'
    repo.mkdir()
    git(repo, 'init', '-q')
    git(repo, 'config', 'user.email', 'test@example.com')
    git(repo, 'config', 'user.name', 'test')
    (repo / 'input.txt').write_text('pinned input\n')
    git(repo, 'add', '.')
    git(repo, 'commit', '-qm', 'initial')
    revision = git(repo, 'rev-parse', 'HEAD')
    monkeypatch.setenv('RVW_SRC_CACHE', str(tmp_path / 'cache'))
    monkeypatch.setattr(source, 'pinned_source_record', lambda name: {'url': str(repo), 'revision': revision})
    return repo, revision


def test_independent_offline_reuse(upstream):
    repo, revision = upstream
    acquired = source.ensure_pinned_source('fixture')
    shutil.rmtree(repo)
    reused = source.ensure_pinned_source('fixture', offline=True)
    assert reused.path == acquired.path
    assert reused.rev == revision
    assert git(reused.path, 'show', 'HEAD:input.txt') == 'pinned input'
    assert not (reused.path / '.git/objects/info/alternates').exists()


def test_offline_miss_never_runs_git(upstream, monkeypatch):
    monkeypatch.setattr(source, 'run_git', lambda *a, **kw: pytest.fail('offline miss ran Git'))
    with pytest.raises(RuntimeError, match='not cached'):
        source.ensure_pinned_source('fixture', offline=True)


def test_modified_cache_is_refused_and_preserved(upstream):
    acquired = source.ensure_pinned_source('fixture')
    (acquired.path / 'input.txt').write_text('changed')
    with pytest.raises(RuntimeError, match='invalid managed source'):
        source.ensure_pinned_source('fixture')
    assert (acquired.path / 'input.txt').read_text() == 'changed'


def test_concurrent_acquisition_publishes_one_complete_tree(upstream):
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: source.ensure_pinned_source('fixture'), range(2)))
    assert results[0].path == results[1].path
    assert results[0].rev == upstream[1]


def test_wrong_pin_does_not_publish(upstream):
    with pytest.raises(RuntimeError, match='acquisition failed'):
        source.ensure_pinned_source('fixture', '0' * 40)
    assert not list(source.src_cache_dir().glob('managed-fixture/*'))
