import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess

import pytest

from race_injection import race_injector
from rvw.common import capture as module
from rvw.common.capture import Capture, CaptureError


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source(tmp_path, name='input', data=b'first'):
    path = tmp_path / name
    path.write_bytes(data)
    return path


def tool(tmp_path):
    path = source(tmp_path, 'my-tool', b'#!/bin/sh\nprintf "version one\\n"\n')
    path.chmod(0o755)
    return path


def test_identity_only_tool_does_not_execute_and_records_linkage(tmp_path):
    marker = tmp_path / 'executed'
    path = source(tmp_path, 'identity-tool', f'#!/bin/sh\ntouch "{marker}"\nexit 1\n'.encode())
    path.chmod(0o755)
    cap = Capture(tmp_path / 'capture')
    item = cap.tool(path, identity_only=True)
    assert not marker.exists()
    assert item.path == path and item.version == ''
    assert cap.tool(path, identity_only=True) is item
    cap.verify_tools()
    record = cap.record()
    assert record['tools'][0]['sha256'] == item.sha256 == sha(path.read_bytes())
    assert record['tools'][0]['copy'] == record['files'][0]['copy']


def test_generated_file_hash_uses_checked_read(tmp_path):
    path = source(tmp_path, data=b'generated')
    assert module.sha256_file(path) == sha(b'generated')
    fifo = tmp_path / 'fifo'
    os.mkfifo(fifo)
    with pytest.raises(ValueError, match='not a regular file'):
        module.sha256_file(fifo)


def test_public_stable_read_can_buffer_a_relative_path(tmp_path, monkeypatch):
    path = source(tmp_path, data=b'checked')
    monkeypatch.chdir(tmp_path)
    digest, size, info, data = module.read_stable(Path('input'), keep=True)
    assert (digest, size, data) == (sha(b'checked'), 7, b'checked')
    assert info.st_ino == path.stat().st_ino


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / 'repo'
    root.mkdir()
    git(root, 'init', '-q')
    git(root, 'config', 'user.email', 'capture@test')
    git(root, 'config', 'user.name', 'Capture Test')
    (root / 'tracked').write_bytes(b'committed')
    (root / '.gitignore').write_text('ignored\n')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'initial')
    return root


def test_file_record_and_raw_gzip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data = gzip.compress(b'wave data')
    path = source(tmp_path, 'trace.gz', data)
    cap = Capture(tmp_path / 'capture')
    item = cap.file(Path('trace.gz'))
    assert item.source == 'trace.gz'
    assert item.resolved == str(path.resolve())
    assert item.copy.is_absolute() and item.copy.name == 'trace.gz'
    assert item.sha256 == sha(data) and item.size == len(data)
    assert item.copy.read_bytes() == data
    assert gzip.decompress(item.copy.read_bytes()) == b'wave data'
    assert cap.root.stat().st_mode & 0o777 == 0o700
    assert item.copy.stat().st_mode & 0o222 == 0
    record = cap.record()
    assert record['files'][0]['sha256'] == item.sha256
    assert record['files'][0]['copy'] == item.copy.relative_to(cap.root).as_posix()
    assert str(cap.root) not in json.dumps(record)
    record['files'].clear()
    assert cap.record()['files']


@pytest.mark.parametrize('replace', [False, True])
def test_edit_and_revert_never_changes_consumed_bytes(tmp_path, race_injector, replace):
    path = source(tmp_path)
    cap = Capture(tmp_path / 'capture')
    first = cap.file(path)
    injection = race_injector.file(cap, 'record', path, b'changed', replace=replace, revert=True)
    assert cap.record()['files'][0]['sha256'] == sha(b'first')
    assert injection.fired and path.read_bytes() == b'first'
    path.write_bytes(b'new live bytes')
    assert cap.file(path) is first
    assert cap.files([path, path]) == [first, first]
    assert first.copy.read_bytes() == b'first'


def test_hash_uses_exact_copy_and_does_not_reopen_live_path(tmp_path, monkeypatch):
    path = source(tmp_path)
    cap = Capture(tmp_path / 'capture')
    original = module.os.read
    count = 0

    def read(fd, size):
        nonlocal count
        if os.fstat(fd).st_ino == path.stat().st_ino:
            count += 1
        return original(fd, size)

    monkeypatch.setattr(module.os, 'read', read)
    item = cap.file(path)
    assert count == 2  # bytes, then EOF, from the same descriptor
    assert item.sha256 == sha(item.copy.read_bytes())
    path.unlink()
    assert cap.file(path) is item
    assert cap.record()['files'][0]['size'] == 5


def test_symlink_retarget_uses_first_target_and_records_link(tmp_path):
    a, b = source(tmp_path, 'a'), source(tmp_path, 'b', b'second')
    link = tmp_path / 'alias'
    link.symlink_to('a')
    cap = Capture(tmp_path / 'capture')
    item = cap.file(link)
    link.unlink()
    link.symlink_to(b)
    assert item.resolved == str(a)
    assert cap.file(link) is item and item.copy.read_bytes() == b'first'
    assert cap.record()['files'][0]['symlinks'] == [{'path': str(link), 'target': 'a'}]


def test_retarget_between_resolution_and_open_uses_resolved_path(tmp_path, race_injector):
    a, b = source(tmp_path, 'a'), source(tmp_path, 'b', b'second')
    link = tmp_path / 'alias'
    link.symlink_to(a)
    cap = Capture(tmp_path / 'capture')

    def retarget():
        link.unlink()
        link.symlink_to(b)

    injection = race_injector.at(module, '_resolve', retarget)
    item = cap.file(link)
    assert injection.fired and item.resolved == str(a) and item.copy.read_bytes() == b'first'


def test_edit_during_read_refuses_and_disables_cache(tmp_path, race_injector):
    path = source(tmp_path)
    cap = Capture(tmp_path / 'capture')
    injection = race_injector.file(module.os, 'read', path, b'other', when='after')
    with pytest.raises(CaptureError, match='input_not_captured:'):
        cap.file(path)
    assert injection.fired
    assert cap.record()['problems']
    assert cap.cache_key({}, complete=True) is None
    assert not list(cap.root.rglob('input'))


@pytest.mark.parametrize('kind', ['missing', 'directory', 'fifo', 'cycle'])
def test_unsupported_file_refuses(tmp_path, kind):
    path = tmp_path / kind
    if kind == 'directory':
        path.mkdir()
    elif kind == 'fifo':
        os.mkfifo(path)
    elif kind == 'cycle':
        path.symlink_to(path)
    cap = Capture(tmp_path / 'capture')
    with pytest.raises(CaptureError) as error:
        cap.file(path)
    assert error.value.status == 'inconclusive'
    assert error.value.cause.startswith('input_not_captured:')
    assert cap.cache_key({}, complete=True) is None


def test_capture_root_must_be_new_and_names_cannot_escape(tmp_path):
    with pytest.raises(CaptureError):
        Capture(tmp_path)
    cap = Capture(tmp_path / 'capture')
    with pytest.raises(CaptureError):
        cap.file(source(tmp_path), name='../escape')
    assert not (tmp_path / 'escape').exists()


def test_environment_and_key_are_explicit_and_stable(tmp_path, monkeypatch):
    monkeypatch.setenv('CAPTURE_FLAGS', '-first')
    monkeypatch.delenv('CAPTURE_UNSET', raising=False)
    path = source(tmp_path)
    cap = Capture(tmp_path / 'one')
    cap.file(path)
    assert cap.env('CAPTURE_FLAGS', 'CAPTURE_UNSET') == {'CAPTURE_FLAGS': '-first', 'CAPTURE_UNSET': None}
    monkeypatch.setenv('CAPTURE_FLAGS', '-second')
    assert cap.env('CAPTURE_FLAGS') == {'CAPTURE_FLAGS': '-first'}
    assert cap.cache_key({'seed': 1}) is None
    key = cap.cache_key({'b': 2, 'a': 1}, complete=True)
    assert key == cap.cache_key({'a': 1, 'b': 2}, complete=True)
    assert key != cap.cache_key({'a': 1, 'b': 3}, complete=True)
    second = Capture(tmp_path / 'two')
    second.file(path)
    second.env('CAPTURE_FLAGS', 'CAPTURE_UNSET')
    assert key != second.cache_key({'a': 1, 'b': 2}, complete=True)
    monkeypatch.setenv('CAPTURE_FLAGS', '-first')
    third = Capture(tmp_path / 'three')
    third.file(path)
    third.env('CAPTURE_FLAGS', 'CAPTURE_UNSET')
    assert key == third.cache_key({'a': 1, 'b': 2}, complete=True)
    with pytest.raises(ValueError):
        cap.cache_key({'bad': float('nan')}, complete=True)


def test_tree_git_copies_dirty_tracked_untracked_and_symlink_targets(tmp_path, repo):
    (repo / 'tracked').write_bytes(b'dirty')
    (repo / 'untracked').write_bytes(b'new')
    (repo / 'ignored').write_bytes(b'not used')
    external = source(tmp_path, 'external', b'outside')
    (repo / 'linked').symlink_to(external)
    executable = repo / 'run'
    executable.write_bytes(b'#!/bin/sh\n')
    executable.chmod(0o755)
    cap = Capture(tmp_path / 'capture')
    tree = cap.tree(repo)
    assert (tree.copy / 'tracked').read_bytes() == b'dirty'
    assert (tree.copy / 'untracked').read_bytes() == b'new'
    assert not (tree.copy / 'ignored').exists()
    assert not (tree.copy / '.git').exists()
    assert not (tree.copy / 'linked').is_symlink()
    assert (tree.copy / 'linked').read_bytes() == b'outside'
    assert (tree.copy / 'run').stat().st_mode & 0o111 == 0o111
    assert tree.size == sum(f.size for f in tree.files)
    assert cap.record()['trees'][0]['sha256'] == tree.sha256
    external.write_bytes(b'changed')
    assert cap.tree(repo) is tree
    assert (tree.copy / 'linked').read_bytes() == b'outside'


def test_plain_tree_materializes_directory_links(tmp_path):
    root = tmp_path / 'tree'
    root.mkdir()
    external = tmp_path / 'external'
    external.mkdir()
    (external / 'header').write_bytes(b'header')
    (root / 'dir').symlink_to(external, target_is_directory=True)
    cap = Capture(tmp_path / 'capture')
    tree = cap.tree(root, git=False)
    assert (tree.copy / 'dir/header').read_bytes() == b'header'
    assert not (tree.copy / 'dir').is_symlink()
    assert cap.record()['trees'][0]['symlinks']


@pytest.mark.parametrize('limit', ['bytes', 'files', 'cycle', 'self', 'not_git', 'submodule'])
def test_tree_refuses_incomplete_or_unbounded_capture(tmp_path, repo, limit):
    options = {'max_tree_bytes': 1} if limit == 'bytes' else {'max_tree_files': 1} if limit == 'files' else {}
    cap = Capture(tmp_path / 'capture', **options)
    root, use_git = repo, True
    if limit == 'cycle':
        (repo / 'cycle').symlink_to(repo, target_is_directory=True)
    elif limit == 'self':
        root, use_git = tmp_path, False
    elif limit == 'not_git':
        root = tmp_path / 'plain'
        root.mkdir()
    elif limit == 'submodule':
        (repo / 'module').mkdir()
        git(repo, 'update-index', '--add', '--cacheinfo', '160000', git(repo, 'rev-parse', 'HEAD'), 'module')
    with pytest.raises(CaptureError, match='input_not_captured:'):
        cap.tree(root, git=use_git)
    assert cap.cache_key({}, complete=True) is None
    assert not cap.record()['trees']


def test_tree_and_file_share_first_read(tmp_path):
    root = tmp_path / 'tree'
    root.mkdir()
    path = source(root)
    cap = Capture(tmp_path / 'capture')
    first = cap.file(path)
    path.write_bytes(b'new')
    tree = cap.tree(root, git=False)
    assert (tree.copy / path.name).read_bytes() == first.copy.read_bytes() == b'first'


def test_git_ref_is_resolved_once_and_pinned(tmp_path, repo, monkeypatch):
    cap = Capture(tmp_path / 'capture')
    head = cap.git_ref(repo, 'HEAD')
    assert head == git(repo, 'rev-parse', 'HEAD')
    (repo / 'tracked').write_bytes(b'next')
    git(repo, 'commit', '-qam', 'next')
    assert cap.git_ref(repo, 'HEAD') == head
    assert cap.git_ref(repo, head) == head
    monkeypatch.setenv('GIT_DIR', str(tmp_path / 'nonexistent'))
    assert cap.git_ref(repo, 'HEAD~1') == head
    assert {entry['commit'] for entry in cap.record()['git_refs']} == {head}
    with pytest.raises(CaptureError):
        cap.git_ref(repo, 'missing')


def test_tool_resolves_path_once_and_binds_version(tmp_path, monkeypatch):
    path = tool(tmp_path)
    monkeypatch.setenv('PATH', str(tmp_path) + os.pathsep + os.environ['PATH'])
    cap = Capture(tmp_path / 'capture')
    item = cap.tool('my-tool')
    assert item.path == path and item.sha256 == sha(path.read_bytes())
    assert item.version == 'version one\n'
    monkeypatch.setenv('PATH', '/does-not-exist')
    assert cap.tool('my-tool') is item
    cap.verify_tools()
    record = cap.record()['tools'][0]
    assert record['path'] == str(path) and record['version'] == item.version


@pytest.mark.parametrize('kind', ['replace', 'edit_revert', 'delete', 'mode'])
def test_changed_tool_refuses_even_after_bytes_revert(tmp_path, race_injector, kind):
    path = tool(tmp_path)
    cap = Capture(tmp_path / 'capture')
    cap.tool(path)
    if kind == 'replace':
        other = source(tmp_path, 'other', b'#!/bin/sh\nexit 0\n')
        other.chmod(0o755)
        os.replace(other, path)
    elif kind == 'edit_revert':
        state = race_injector.file(cap, 'record', path, b'#!/bin/sh\nexit 1\n', revert=True)
        cap.record()
        assert state.fired
    elif kind == 'delete':
        path.unlink()
    else:
        path.chmod(0o644)
    with pytest.raises(CaptureError):
        cap.verify_tools()
    assert cap.cache_key({}, complete=True) is None


def test_tool_change_during_version_refuses(tmp_path, race_injector):
    path = tool(tmp_path)
    cap = Capture(tmp_path / 'capture')
    injection = race_injector.file(module, 'run_group', path, b'#!/bin/sh\nexit 0\n', when='after')
    with pytest.raises(CaptureError):
        cap.tool(path)
    assert injection.fired


def test_version_uses_process_group_and_bound(tmp_path, monkeypatch):
    path = tool(tmp_path)
    cap = Capture(tmp_path / 'capture')
    called = []
    real = module.run_group

    def run(argv, **kwargs):
        called.append((argv, kwargs))
        return real(argv, **kwargs)

    monkeypatch.setattr(module, 'run_group', run)
    cap.tool(path)
    assert called[0][0] == [str(path), '--version']
    assert called[0][1]['timeout'] == 10


def test_tree_leaf_resolves_symlink_once(tmp_path, race_injector):
    root = tmp_path / 'tree'
    root.mkdir()
    a, b = source(tmp_path, 'a'), source(tmp_path, 'b', b'second')
    link = root / 'alias'
    link.symlink_to(a)
    cap = Capture(tmp_path / 'capture')

    def retarget():
        link.unlink()
        link.symlink_to(b)

    injection = race_injector.at(module, '_resolve', retarget, occurrence=2)
    tree = cap.tree(root, git=False)
    assert injection.fired
    assert (tree.copy / 'alias').read_bytes() == b'first'
    assert tree.files[0].resolved == str(a)


def test_tool_version_failure_disables_cache(tmp_path, monkeypatch):
    from rvw.common.proc import Result
    path = tool(tmp_path)
    cap = Capture(tmp_path / 'capture')
    monkeypatch.setattr(module, 'run_group', lambda *a, **kw: Result(124, True, 'partial', ''))
    with pytest.raises(CaptureError):
        cap.tool(path)
    assert cap.cache_key({}, complete=True) is None


def test_record_order_does_not_depend_on_capture_order(tmp_path):
    a, b = source(tmp_path, 'a'), source(tmp_path, 'b')
    first, second = Capture(tmp_path / 'one'), Capture(tmp_path / 'two')
    first.files([a, b])
    second.files([b, a])
    assert first.record() == second.record()
    assert first.cache_key({}, complete=True) == second.cache_key({}, complete=True)


def test_symlink_dot_dot_follows_filesystem_semantics(tmp_path):
    real = tmp_path / 'real'
    (real / 'child').mkdir(parents=True)
    (real / 'input').write_bytes(b'real')
    (tmp_path / 'input').write_bytes(b'wrong')
    (tmp_path / 'link').symlink_to(real / 'child', target_is_directory=True)
    cap = Capture(tmp_path / 'capture')
    item = cap.file(tmp_path / 'link/../input')
    assert item.copy.read_bytes() == b'real'
    assert item.resolved == str(real / 'input')


def test_cache_key_tracks_empty_directories(tmp_path):
    root = tmp_path / 'tree'
    root.mkdir()
    source(root)
    first = Capture(tmp_path / 'one')
    before = first.tree(root, git=False)
    (root / 'empty').mkdir()
    second = Capture(tmp_path / 'two')
    after = second.tree(root, git=False)
    assert before.sha256 != after.sha256
    assert first.cache_key({}, complete=True) != second.cache_key({}, complete=True)
    assert after.directories == ('empty',)
    assert second.record()['trees'][0]['directories'] == ['empty']


def test_empty_directories_count_against_tree_limit(tmp_path):
    root = tmp_path / 'tree'
    (root / 'a').mkdir(parents=True)
    (root / 'b').mkdir()
    cap = Capture(tmp_path / 'capture', max_tree_files=1)
    with pytest.raises(CaptureError):
        cap.tree(root, git=False)


def test_directory_symlink_target_is_pinned_before_traversal(tmp_path, race_injector):
    root = tmp_path / 'tree'
    root.mkdir()
    a, b = tmp_path / 'a', tmp_path / 'b'
    a.mkdir()
    b.mkdir()
    source(a, data=b'first')
    source(b, data=b'second')
    link = root / 'directory'
    link.symlink_to(a, target_is_directory=True)
    cap = Capture(tmp_path / 'capture')

    def retarget():
        link.unlink()
        link.symlink_to(b, target_is_directory=True)

    injection = race_injector.at(module, '_resolve', retarget, occurrence=2)
    tree = cap.tree(root, git=False)
    assert injection.fired
    assert (tree.copy / 'directory/input').read_bytes() == b'first'
    assert tree.files[0].resolved == str(a / 'input')


def test_replaced_file_is_not_executed_for_tool_version(tmp_path, monkeypatch):
    path = tool(tmp_path)
    cap = Capture(tmp_path / 'capture')
    cap.file(path)
    path.write_bytes(b'#!/bin/sh\nexit 0\n')
    calls = []
    monkeypatch.setattr(module, 'run_group', lambda *a, **kw: calls.append(a))
    with pytest.raises(CaptureError):
        cap.tool(path)
    assert not calls


def test_race_fixture_restores_after_exception(tmp_path, race_injector):
    path = source(tmp_path)

    class Reader:
        def read(self):
            assert path.read_bytes() == b'temporary'
            raise ValueError('failed during read')

    reader = Reader()
    injection = race_injector.file(reader, 'read', path, b'temporary', replace=True, revert=True)
    with pytest.raises(ValueError, match='failed during read'):
        reader.read()
    assert injection.fired and injection.calls == 1
    assert path.read_bytes() == b'first'


def test_new_symlink_in_resolved_parent_refuses_capture(tmp_path, race_injector):
    real, alternate = tmp_path / 'real', tmp_path / 'alternate'
    real.mkdir()
    alternate.mkdir()
    path = source(real)
    source(alternate, data=b'other')
    cap = Capture(tmp_path / 'capture')

    def replace_parent():
        real.rename(tmp_path / 'old-real')
        real.symlink_to(alternate, target_is_directory=True)

    injection = race_injector.at(module, '_resolve', replace_parent)
    with pytest.raises(CaptureError):
        cap.file(path)
    assert injection.fired


@pytest.mark.parametrize('options', [{1: 'one'}, {'nested': [{1: 'one'}]}])
def test_cache_key_refuses_non_string_json_keys(tmp_path, options):
    cap = Capture(tmp_path / 'capture')
    with pytest.raises(ValueError, match='string'):
        cap.cache_key(options, complete=True)


def test_partial_file_enumeration_disables_caching(tmp_path):
    cap = Capture(tmp_path / 'capture')
    path = source(tmp_path)

    def paths():
        yield path
        raise OSError('file list became unreadable')

    with pytest.raises(CaptureError, match='input_not_captured:files'):
        cap.files(paths())
    assert cap.cache_key({}, complete=True) is None


@pytest.fixture
def tmp_path(external_tmp_path):
    return external_tmp_path
