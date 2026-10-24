"""Direct C3 paths must validate their owning run set."""
import json
import shutil

import pytest

from rvw.regress.config import load_config
from rvw.regress.plan import suites_plan
from rvw.regress.runner import RunOptions, Runner
from rvw.regress.source import describe
from rvw.results import SchemaError, find_results, load_results


def _run(fake, out):
    core = load_config(str(fake.config))
    Runner(core, describe(fake.repo), out, RunOptions(log=None, index=False)).run(
        suites_plan(core, ["isa"], None))
    # These tests exercise the supported legacy layout. New-generation tests are separate.
    (out / "current").unlink()
    from rvw.results.generation import _discard
    _discard(out / "generations")
    return out / "isa" / "small"


def _break(out, defect):
    path = out / "run.json"
    manifest = json.loads(path.read_text())
    if defect == "missing":
        path.unlink()
        return
    if defect == "unfinished":
        manifest["finished"] = None
    elif defect == "unlisted":
        manifest["results"] = []
    elif defect == "source":
        manifest["source"]["core_rev_full"] = "wrong"
    elif defect == "source_missing":
        manifest.pop("source")
    elif defect == "source_empty":
        manifest["source"] = {}
    elif defect == "source_bad":
        manifest["source"] = "unknown"
    elif defect == "core":
        manifest["core"] = "wrong"
    elif defect == "run_id":
        manifest["run_id"] = "another-run"
    elif defect == "schema":
        manifest["schema"] = "wrong"
    path.write_text(json.dumps(manifest))


@pytest.mark.parametrize("defect", ["unfinished", "missing", "unlisted", "source", "source_missing",
                                    "source_empty", "source_bad", "core", "run_id", "schema"])
@pytest.mark.parametrize("as_file", [False, True])
def test_direct_suite_validates_owner(fake, tmp_path, defect, as_file):
    out = tmp_path / "run"
    suite = _run(fake, out)
    _break(out, defect)
    with pytest.raises((SchemaError, FileNotFoundError)):
        load_results(suite / "results.json" if as_file else suite)
    with pytest.raises((SchemaError, FileNotFoundError)):
        find_results(suite)


@pytest.mark.parametrize("reader", ["compare", "gate", "mcp", "coverage"])
def test_direct_unfinished_suite_refused_by_all_readers(fake, rvw, tmp_path, reader):
    base = tmp_path / "base"
    _run(fake, base)
    out = tmp_path / "candidate"
    suite = _run(fake, out)
    # A resumed invocation clears finished before replacing old suite results.
    _break(out, "unfinished")
    if reader == "coverage":
        from rvw.cov.code import inputs
        with pytest.raises(SchemaError, match="incomplete"):
            inputs([str(suite)])
    elif reader == "mcp":
        from rvw.mcp.registry import Registry
        registry, errors = Registry.discover({"regress"})
        assert not errors
        _, _, error = registry.call_json("regress_compare", {"base": str(base), "candidate": str(suite)})
        assert error
    else:
        args = (base, suite) if reader == "compare" else (
            "--core", fake.config, "--base", base, "--cand", suite)
        code, _, _ = rvw("regress", reader, *args, "--json")
        assert code == 2


def test_direct_suite_inherits_full_owner_identity(fake, tmp_path):
    out = tmp_path / "run"
    suite = _run(fake, out)
    path = suite / "results.json"
    old = json.loads(path.read_text())
    full = old["source"].pop("core_rev_full")
    path.write_text(json.dumps(old))
    assert load_results(suite).source["core_rev_full"] == full


def test_suite_symlink_cannot_escape_owner(fake, tmp_path):
    out = tmp_path / "run"
    suite = _run(fake, out)
    moved = tmp_path / "moved"
    suite.rename(moved)
    suite.symlink_to(moved, target_is_directory=True)
    with pytest.raises(SchemaError):
        find_results(out)


def test_legacy_runner_suite_with_missing_owner_is_refused(fake, tmp_path):
    out = tmp_path / "run"
    suite = _run(fake, out)
    path = suite / "results.json"
    old = json.loads(path.read_text())
    old.pop("run_set")
    path.write_text(json.dumps(old))
    (out / "run.json").unlink()
    with pytest.raises(SchemaError, match="owning run set is missing"):
        load_results(suite)


def test_detached_legacy_runner_c3_requires_owner(fake, tmp_path):
    out = tmp_path / "run"
    suite = _run(fake, out)
    old = json.loads((suite / "results.json").read_text())
    old.pop("run_set")
    detached = tmp_path / "detached"
    detached.mkdir()
    (detached / "results.json").write_text(json.dumps(old))
    with pytest.raises(SchemaError, match="owning run set is missing"):
        load_results(detached)


@pytest.mark.parametrize("kind", ["directory", "file"])
@pytest.mark.parametrize("reader", ["direct", "root"])
@pytest.mark.parametrize("owner_state", ["complete", "unfinished", "missing", "broken"])
def test_suite_alias_cannot_borrow_another_owner(fake, tmp_path, kind, reader, owner_state):
    base = _run(fake, tmp_path / "base")
    out = tmp_path / "candidate"
    suite = _run(fake, out)
    # A copied run keeps its run_id. Matching metadata does not permit an escaping alias.
    manifest_path = out / "run.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["run_id"] = json.loads((base / "results.json").read_text())["run_id"]
    if owner_state == "unfinished":
        manifest["finished"] = None
    manifest_path.write_text(json.dumps(manifest))
    if kind == "directory":
        shutil.rmtree(suite)
        suite.symlink_to(base, target_is_directory=True)
    else:
        (suite / "results.json").unlink()
        (suite / "results.json").symlink_to(base / "results.json")
    if owner_state in ("missing", "broken"):
        manifest_path.unlink()
        if owner_state == "broken":
            manifest_path.symlink_to(out / "missing-manifest.json")
    # A tree walk skips directory links when no root manifest remains; no evidence is found.
    if reader == "root" and kind == "directory" and owner_state in ("missing", "broken"):
        assert not find_results(out)
        return
    with pytest.raises((SchemaError, FileNotFoundError)):
        if reader == "direct":
            load_results(suite)
        else:
            find_results(out)
