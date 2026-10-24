"""Ordinary tracked deletions remain usable, dirty execution inputs."""
import shutil
import subprocess

import pytest

from rvw.common.capture import Capture, CaptureError
from rvw.regress.compare import compare
from rvw.regress.config import load_config
from rvw.regress.plan import suites_plan
from rvw.regress.runner import Runner, RunOptions
from rvw.regress.source import describe
from rvw.results import find_results
from test_capture_round22 import helper


def deleted_source(fake, *, parent=True):
    path = fake.repo / 'old/obsolete.scala'
    path.parent.mkdir()
    path.write_text('// removed source\n')
    fake.commit({}, msg='old source')
    if parent:
        shutil.rmtree(path.parent)
    else:
        path.unlink()
    return path


@pytest.mark.parametrize('parent', [False, True])
def test_git_tree_records_tracked_deletion(fake, tmp_path, parent):
    deleted_source(fake, parent=parent)
    cap = Capture(tmp_path / 'capture')
    tree = cap.tree(fake.repo)
    assert tree.deleted == ('old/obsolete.scala',)
    assert cap.record()['trees'][0]['deleted'] == ['old/obsolete.scala']
    assert not (tree.copy / 'old').exists()
    assert all(not item.source.endswith('obsolete.scala') for item in tree.files)


def test_deletions_affect_identity_and_entry_limit(fake, tmp_path):
    deleted_source(fake)
    cap = Capture(tmp_path / 'capture')
    tree = cap.tree(fake.repo)
    subprocess.run(['git', '-C', str(fake.repo), 'add', '-u'], check=True)
    other = Capture(tmp_path / 'other')
    assert other.tree(fake.repo).sha256 != tree.sha256
    assert other.cache_key({}, complete=True) != cap.cache_key({}, complete=True)
    # All remaining entries plus the deleted inventory entry count toward the limit.
    subprocess.run(['git', '-C', str(fake.repo), 'reset', '-q', 'HEAD'], check=True)
    limited = Capture(tmp_path / 'limited', max_tree_files=len(tree.files))
    with pytest.raises(CaptureError, match='entry-count limit'):
        limited.tree(fake.repo)
    assert limited.cache_key({}, complete=True) is None


@pytest.mark.parametrize('kind', ['leaf_link', 'parent_link', 'unreadable'])
def test_git_tree_does_not_treat_unreadable_inputs_as_deleted(fake, tmp_path, monkeypatch, kind):
    deleted = deleted_source(fake)
    if kind == 'leaf_link':
        deleted.parent.mkdir()
        deleted.symlink_to(tmp_path / 'absent')
    elif kind == 'parent_link':
        deleted.parent.symlink_to(tmp_path / 'absent', target_is_directory=True)
    else:
        import rvw.common.capture as module
        original = module._open_read
        def deny(path):
            if path == fake.repo / 'counter':
                raise PermissionError('unreadable source')
            return original(path)
        monkeypatch.setattr(module, '_open_read', deny)
    cap = Capture(tmp_path / 'capture')
    with pytest.raises(CaptureError):
        cap.tree(fake.repo)
    assert cap.cache_key({}, complete=True) is None


def test_deleted_tree_runs_without_accept_or_cache(fake, tmp_path):
    deleted_source(fake)
    core = load_config(str(fake.config))
    runner = Runner(core, describe(fake.repo), tmp_path / 'out', RunOptions(index=False, log=None))
    summary = runner.run(suites_plan(core, ['isa'], None))
    assert summary['ok'], runner.inputs.problem
    assert fake.calls('run')
    assert summary['source']['core_dirty'] is True
    assert not runner.cacheable
    assert not list(runner.cache.dir.rglob('result.json'))
    suites = find_results(runner.out)
    verdict = compare(suites, suites)
    assert verdict.verdict == 'inconclusive'
    assert verdict.extra['inconclusive_cause'] == 'candidate_not_committed'
