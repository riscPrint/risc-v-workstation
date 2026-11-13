"""Revision checkouts of a core repository that uses git submodules (VexiiRiscv pins SpinalHDL so)."""
import subprocess

import pytest

from rvw.regress import source

ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
       "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"}


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "protocol.file.allow=always", *args], check=True,
                          capture_output=True, text=True, env=ENV).stdout.strip()


def commit(repo, name, text):
    (repo / name).write_text(text)
    git(repo, "add", name)
    git(repo, "commit", "-qm", name)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def core(tmp_path, monkeypatch):
    monkeypatch.setenv("RVW_SRC_CACHE", str(tmp_path / "cache"))
    lib = tmp_path / "lib"
    lib.mkdir()
    git(lib, "init", "-q")
    old = commit(lib, "lib.txt", "v1\n")
    new = commit(lib, "lib.txt", "v2\n")
    repo = tmp_path / "core"
    repo.mkdir()
    git(repo, "init", "-q")
    commit(repo, "core.txt", "core\n")
    git(repo, "submodule", "-q", "add", str(lib), "ext/lib")
    git(repo, "-C", "ext/lib", "checkout", "-q", old)
    git(repo, "add", "ext/lib")
    git(repo, "commit", "-qm", "pin lib v1")
    base = git(repo, "rev-parse", "HEAD")
    git(repo, "-C", "ext/lib", "checkout", "-q", new)
    git(repo, "add", "ext/lib")
    git(repo, "commit", "-qm", "pin lib v2")
    return repo, base, lib


def test_revision_checkout_contains_the_pinned_submodule(core):
    repo, base, _ = core
    tree = source.checkout(repo, base, "fake")
    assert (tree.path / "ext/lib/lib.txt").read_text() == "v1\n"
    assert not tree.dirty
    head = source.checkout(repo, "HEAD", "fake")
    assert (head.path / "ext/lib/lib.txt").read_text() == "v2\n"


def test_uninitialized_submodule_stays_empty(core, tmp_path):
    repo, base, _ = core
    bare = tmp_path / "plain"
    subprocess.run(["git", "clone", "-q", str(repo), str(bare)], check=True, env=ENV)
    tree = source.checkout(bare, base, "plain")
    assert not any((tree.path / "ext/lib").iterdir())


def test_missing_pinned_submodule_commit_is_an_error(core, tmp_path):
    repo, base, lib = core
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(repo), str(other)], check=True, env=ENV)
    fresh = other / "ext/lib"
    fresh.rmdir()
    # A submodule repository that lacks the commit the base revision records.
    git(tmp_path, "init", "-q", str(fresh))
    commit(fresh, "unrelated.txt", "x\n")
    with pytest.raises(RuntimeError, match="submodule ext/lib"):
        source.checkout(other, base, "missing")
