"""A selected checkout must reach the adapter and agree with its C1 provenance."""
from regress_fixtures import legacy_layout
import json

import pytest

from rvw.regress.config import ConfigError, load_config
from rvw.regress.plan import source_for, suites_plan
from rvw.regress.runner import RunOptions, Runner
from rvw.regress.source import describe
from rvw.results import find_results, load_run, save_run


@pytest.mark.parametrize("selection", ["revision", "path", "runner"])
def test_selected_sources_require_source_env(fake, tmp_path, selection):
    core = load_config(str(fake.config))
    core.source_env = None
    src = describe(fake.repo)
    with pytest.raises(ConfigError, match="source_env"):
        if selection == "revision":
            source_for(core, src.rev)
        elif selection == "path":
            source_for(core, None, fake.repo)
        else:
            Runner(core, src, tmp_path / "run", RunOptions(log=None))
    assert not fake.calls()


@pytest.mark.parametrize("field,value", [
    ("core_repo", "/wrong/checkout"), ("core_rev", "0" * 7),
    ("core_rev_full", "0" * 40), ("core_dirty", True),
    ("core_fingerprint", "wrong"), ("core_links", "wrong"),
    ("core_identity_covered", False),
])
@pytest.mark.parametrize("reuse", ["fresh", "resume", "cache"])
def test_conflicting_c1_provenance_is_inconclusive(fake, tmp_path, monkeypatch, field, value, reuse):
    core = load_config(str(fake.config))
    src = describe(fake.repo)
    out = tmp_path / "first"
    opts = RunOptions(log=None, index=False)
    r = Runner(core, src, out, opts)
    plan = suites_plan(core, ["isa"], None)

    def poison(path):
        result = load_run(path)
        result.source[field] = value
        save_run(result, path)

    if reuse == "fresh":
        actual = r._run_tests
        def run(*args):
            actual(*args)
            for path in out.rglob("result.json"):
                poison(path.parent)
        monkeypatch.setattr(r, "_run_tests", run)
    else:
        assert r.run(plan)["ok"]
        legacy_layout(out)
        for pointer in list(r.cache.dir.rglob("current")):
            legacy_layout(pointer.parent)
        if reuse == "resume":
            for path in out.rglob("result.json"):
                poison(path.parent)
        else:
            for path in r.cache.dir.rglob("result.json"):
                poison(path.parent)
            out = tmp_path / "restored"
        r = Runner(core, src, out, opts)
    result = r.run(plan)
    # Reused conflicts may instead be discarded and rerun with truthful adapter provenance.
    entries = [entry for res in find_results(out) for entry in res.tests]
    if result["ok"]:
        assert reuse != "fresh"
        assert all(load_run(res.path / t.run).source.get(field) != value
                   for res in find_results(out) for t in res.tests)
    else:
        assert result["inconclusive"] == 3
        assert all(not t.conclusive for t in entries)
        assert all(load_run(res.path / t.run).why_inconclusive
                   for res in find_results(out) for t in res.tests)
    for path in r.cache.dir.rglob("result.json"):
        data = json.loads(path.read_text())
        # An old conflict may remain in immutable cache storage; no newly trusted conflict exists.
        if reuse == "fresh":
            assert data["source"].get(field) != value


def test_cache_reuse_requires_captured_provenance(fake, tmp_path):
    from rvw.regress.source import checkout
    from rvw.results import RunResult
    core = load_config(str(fake.config))
    selected = describe(fake.repo)
    other = checkout(fake.repo, selected.rev, "fake")
    runner = Runner(core, selected, tmp_path / "run", RunOptions(log=None))
    # Another checkout cannot substitute for the selected source.
    c1 = RunResult(status="pass", source=other.to_dict())
    assert runner._provenance_error(c1)


@pytest.mark.parametrize("missing", ["core_repo", "core_rev"])
def test_selected_source_requires_c1_path_and_revision(fake, tmp_path, missing):
    from rvw.results import RunResult
    core = load_config(str(fake.config))
    selected = describe(fake.repo)
    recorded = selected.to_dict()
    recorded.pop(missing)
    if missing == "core_rev":
        recorded.pop("core_rev_full")
    runner = Runner(core, selected, tmp_path / "run", RunOptions(log=None))
    assert runner._provenance_error(RunResult(status="pass", source=recorded))
