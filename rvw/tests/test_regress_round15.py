"""Round-15 review findings in `rvw regress`: a killed run's adapter still writing into --out, a
modified source-cache checkout reused for --base-rev, and compare pooling results of different
sources or duplicate (test, seed) entries."""
import json

import pytest

from rvw.regress import source
from rvw.regress.config import load_config
from rvw.regress.plan import gate
from rvw.regress.runner import RunOptions


# ------------------------------------------------------------------------------ source cache

@pytest.fixture
def two_revs(fake):
    """A fake core whose base passes and whose candidate fails rv64ui-p-add."""
    (fake.repo / ".gitignore").write_text("target/\n")
    base = fake.commit(msg="base")
    cand = fake.commit({"rv64ui-p-add": "status=fail fail_code=9"}, msg="broken")
    return fake, base, cand, load_config(str(fake.config))


def _gate(core, base):
    v = gate(core, "quick", base, None, None, None, None,
             RunOptions(use_cache=False, index=False, log=None), None, None)["verdict"]
    return v


@pytest.mark.parametrize("change", ["untracked", "edited", "head"])
def test_modified_cached_checkout_is_not_reused_for_base_rev(two_revs, change):
    """The done mark alone made a cached checkout count as `base`: an added file, an edit, or a
    moved HEAD turned the base into the failing candidate and the gate accepted (still failing)."""
    f, base, cand, core = two_revs
    assert _gate(core, base).verdict == "reject"
    s = source.checkout(f.repo, base, core.name)
    if change == "untracked":
        (s.path / "overrides.json").write_text(json.dumps({"rv64ui-p-add": "status=fail fail_code=9"}))
    elif change == "edited":
        (s.path / "overrides.json").write_text(json.dumps({"rv64ui-p-add": "status=fail fail_code=9"}))
        assert source.run_group(["git", "-C", str(s.path), "add", "overrides.json"], timeout=5).returncode == 0
    else:
        assert source.run_group(["git", "-C", str(s.path), "checkout", "-q", "--force", "--detach", cand],
                                timeout=5).returncode == 0
    v = _gate(core, base)
    assert v.verdict == "reject" and len(v.new_failures) == 1
    assert v.extra["base"]["core_rev"] == base[:7]
    # The modified tree is left as it was (it may be in use); a fresh one was made beside it.
    fresh = source.checkout(f.repo, base, core.name)
    assert fresh.path != s.path and fresh.path.name == f"{base[:12]}-2"
    assert fresh.rev == base and not fresh.dirty
    assert (s.path / ".git" / source.DONE_MARK).is_file()
    if change != "head":
        assert (s.path / "overrides.json").is_file()


def test_clean_cached_checkout_is_still_reused(two_revs):
    f, base, _, core = two_revs
    a = source.checkout(f.repo, base, core.name)
    (a.path / "target").mkdir()          # ignored build output is fine
    (a.path / "target" / "x.class").write_text("built")
    b = source.checkout(f.repo, base, core.name)
    assert b.path == a.path and not b.dirty


def test_all_slots_modified_is_refused(two_revs, monkeypatch):
    f, base, _, core = two_revs
    monkeypatch.setattr(source, "CHECKOUT_SLOTS", 2)
    for _ in range(2):
        s = source.checkout(f.repo, base, core.name)
        (s.path / "stray.txt").write_text("x")
    with pytest.raises(RuntimeError, match="no clean checkout"):
        source.checkout(f.repo, base, core.name)


@pytest.mark.parametrize("change", ["edit", "delete"])
def test_cached_checkout_rechecks_tracked_files(two_revs, change):
    f, base, _, core = two_revs
    cached = source.checkout(f.repo, base, core.name)
    tracked = cached.path / "counter"
    if change == "edit":
        tracked.write_text("changed after publication")
    else:
        tracked.unlink()
    fresh = source.checkout(f.repo, base, core.name)
    assert fresh.path != cached.path and fresh.rev == base and not fresh.dirty
    assert (fresh.path / "counter").read_text() == "base"
    assert tracked.exists() == (change == "edit")
