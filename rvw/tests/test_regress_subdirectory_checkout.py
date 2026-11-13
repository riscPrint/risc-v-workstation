"""A core project can live below the root of its source repository."""
import subprocess
import pytest
from rvw.regress.source import checkout

pytestmark = pytest.mark.fast


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def test_revision_selection_preserves_core_subdirectory(tmp_path, monkeypatch):
    repo = tmp_path / 'repository'
    repo.mkdir()
    git(repo, 'init', '-q')
    git(repo, 'config', 'user.name', 'Test')
    git(repo, 'config', 'user.email', 'test@example.invalid')
    core = repo / 'examples' / 'small'
    core.mkdir(parents=True)
    (core / 'core.scala').write_text('old RTL\n')
    (repo / 'shared.txt').write_text('shared dependency\n')
    git(repo, 'add', '.')
    git(repo, 'commit', '-qm', 'initial')
    revision = git(repo, 'rev-parse', 'HEAD')
    (core / 'core.scala').write_text('new dirty RTL\n')
    monkeypatch.setenv('RVW_SRC_CACHE', str(tmp_path / 'cache'))
    selected = checkout(core, revision, 'small')
    assert selected.path.is_dir()
    assert selected.path.parts[-2:] == ('examples', 'small')
    assert (selected.path / 'core.scala').read_text() == 'old RTL\n'
    assert (selected.path.parent.parent / 'shared.txt').is_file()
    assert selected.rev == revision
    assert not selected.dirty
    assert (core / 'core.scala').read_text() == 'new dirty RTL\n'
