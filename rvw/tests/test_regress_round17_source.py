"""Source identity must include bytes hidden by Git index and ignore settings."""
import os
import subprocess

import pytest

from rvw.regress import source
from rvw.common.capture import Capture


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_hidden_tracked_edit_changes_core_and_cache_paths(fake, tmp_path, flag):
    before = source.describe(fake.repo)
    tools = Capture(tmp_path / "capture-0").file(fake.repo / "counter").sha256
    git(fake.repo, "update-index", flag, "counter")
    (fake.repo / "counter").write_text("hidden edit")
    assert git(fake.repo, "status", "--porcelain") == ""
    after = source.describe(fake.repo)
    assert after.dirty and after.fingerprint != before.fingerprint
    changed = Capture(tmp_path / "capture-1").file(fake.repo / "counter").sha256
    assert changed != tools
    (fake.repo / "counter").write_text("second edit")
    assert source.describe(fake.repo).fingerprint != after.fingerprint
    assert Capture(tmp_path / "capture-2").file(fake.repo / "counter").sha256 != changed


@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_hidden_cached_checkout_edit_is_not_selected(fake, flag):
    rev = git(fake.repo, "rev-parse", "HEAD")
    first = source.checkout(fake.repo, rev, "fake")
    git(first.path, "update-index", flag, "counter")
    (first.path / "counter").write_text("hidden edit")
    second = source.checkout(fake.repo, rev, "fake")
    assert second.path != first.path and not second.dirty
    assert (first.path / "counter").read_text() == "hidden edit"


@pytest.mark.parametrize("where", ["info", "global"])
def test_private_ignore_rules_cannot_hide_source_bytes(fake, tmp_path, where):
    before = Capture(tmp_path / "capture-3").tree(fake.repo, git=True).sha256
    if where == "info":
        rules = fake.repo / ".git" / "info" / "exclude"
    else:
        rules = tmp_path / "excludes"
        git(fake.repo, "config", "core.excludesFile", str(rules))
    rules.write_text("hidden.scala\n")
    (fake.repo / "hidden.scala").write_text("first")
    assert git(fake.repo, "status", "--porcelain") == ""
    a = source.describe(fake.repo)
    tools = Capture(tmp_path / "capture-4").tree(fake.repo, git=True).sha256
    assert a.dirty and tools != before
    (fake.repo / "hidden.scala").write_text("second")
    assert source.describe(fake.repo).fingerprint != a.fingerprint
    assert Capture(tmp_path / "capture-5").tree(fake.repo, git=True).sha256 != tools


@pytest.mark.parametrize("feature", ["sparse", "replace", "graft", "shallow", "filter"])
def test_unverified_git_features_are_refused(fake, feature):
    rev = git(fake.repo, "rev-parse", "HEAD")
    if feature == "sparse":
        git(fake.repo, "config", "core.sparseCheckout", "true")
    elif feature == "replace":
        git(fake.repo, "update-ref", "refs/replace/" + rev, rev)
    elif feature == "graft":
        (fake.repo / ".git" / "info" / "grafts").write_text(rev + "\n")
    elif feature == "shallow":
        (fake.repo / ".git" / "shallow").write_text(rev + "\n")
    else:
        git(fake.repo, "config", "filter.hidden.clean", "cat")
        (fake.repo / ".gitattributes").write_text("counter filter=hidden\n")
    with pytest.raises(ValueError, match="source identity"):
        source.describe(fake.repo)
    with pytest.raises(ValueError, match="source identity"):
        source.checkout(fake.repo, rev, "fake")


def test_filemode_false_cannot_hide_execute_bit(fake):
    git(fake.repo, "config", "core.fileMode", "false")
    p = fake.repo / "counter"
    original = p.stat().st_mode
    p.chmod(original | 0o111)
    assert git(fake.repo, "status", "--porcelain") == ""
    assert source.describe(fake.repo).dirty


def test_autocrlf_cannot_hide_raw_byte_changes(fake):
    p = fake.repo / "counter"
    p.write_bytes(b"base\n")
    git(fake.repo, "-c", "core.autocrlf=false", "add", "counter")
    git(fake.repo, "commit", "-qm", "LF source")
    git(fake.repo, "config", "core.autocrlf", "true")
    p.unlink()
    git(fake.repo, "checkout", "--", "counter")
    assert p.read_bytes() == b"base\r\n"
    assert git(fake.repo, "status", "--porcelain") == ""
    assert source.describe(fake.repo).dirty


@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_hidden_edit_cannot_reuse_a_cached_pass(fake, rvw, tmp_path, flag):
    fake.commit({"rv64ui-p-add": "status=pass"}, msg="tracked directives")
    args = ("regress", "run", "--core", fake.config, "--suite", "isa", "--json")
    assert rvw(*args, "--out", tmp_path / "first")[0] == 0
    git(fake.repo, "update-index", flag, "overrides.json")
    (fake.repo / "overrides.json").write_text('{"rv64ui-p-add": "status=fail fail_code=7"}')
    code, _, result = rvw(*args, "--out", tmp_path / "second")
    assert code == 1 and result["counts"] == {"pass": 2, "fail": 1}
    from rvw.results import find_results
    assert all(not t.extra.get("cached") for r in find_results(tmp_path / "second") for t in r.tests)
