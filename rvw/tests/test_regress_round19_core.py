"""A different core cannot supply a baseline or a core-scoped latest run."""
from pathlib import Path

import pytest

from rvw.regress.cli import execute_json
from rvw.regress.compare import compare
from rvw.regress.store import append_index, resolve_run
from rvw.results import SuiteResults, TestEntry, save_results

HERE = Path(__file__).resolve().parent


def _results(core, status="fail"):
    return SuiteResults("run", "isa", core, "small", "now",
                        source={"core_rev": "abc", "core_rev_full": "a" * 40, "core_dirty": False},
                        tests=[TestEntry("test", status, seed=1,
                                         signature="fail:7" if status == "fail" else None,
                                         extra={"elf_sha256": "a" * 64, "options": {}})])


@pytest.mark.parametrize("status", ["pass", "fail"])
def test_compare_refuses_different_cores(status):
    with pytest.raises(ValueError, match="core"):
        compare([_results("coreA", status)], [_results("coreB", status)])


def test_compare_refuses_missing_core_name():
    with pytest.raises(ValueError, match="core"):
        compare([_results("")], [_results("")])


@pytest.mark.parametrize("action", ["compare", "gate"])
@pytest.mark.parametrize("other_candidate", [False, True])
def test_requested_core_must_match_both_sides(fake, rvw, tmp_path, action, other_candidate):
    base, cand = tmp_path / "base", tmp_path / "cand"
    save_results(_results("coreA"), base)
    save_results(_results("coreB" if other_candidate else "coreA"), cand)
    args = (base, cand) if action == "compare" else ("--base", base, "--cand", cand)
    code, _, data = rvw("regress", action, *args, "--core", fake.config, "--json")
    assert code == 2 and data is None and "core" in rvw.stderr
    assert not (cand / "verdict.json").exists()


def test_compare_same_core_remains_valid():
    res = [_results("coreA")]
    assert compare(res, res).verdict == "accept"


def test_latest_resolution_uses_requested_core(tmp_path):
    for core in ("coreB", "coreA"):
        append_index({"core": core, "run_id": core, "path": str(tmp_path / core)}, tmp_path)
    assert resolve_run("latest", tmp_path, core="coreB") == tmp_path / "coreB"
    with pytest.raises(ValueError, match="coreC"):
        resolve_run("latest", tmp_path, core="coreC")


def test_gate_latest_uses_older_baseline_of_requested_core(fake, tmp_path):
    base = tmp_path / "baseB"
    execute_json("run", core=str(fake.config), tier="quick", out=str(base), no_cache=True)
    fake.commit({"rv64ui-p-add": "status=fail fail_code=7"}, msg="broken")
    adapter = tmp_path / "coreA_adapter.py"
    adapter.write_text((HERE / "fake_adapter.py").read_text().replace('"core": "fake"', '"core": "coreA"'))
    other = tmp_path / "coreA.toml"
    other.write_text(fake.config.read_text().replace('name = "fake"', 'name = "coreA"').replace(
        str(HERE / "fake_adapter.py"), str(adapter)))
    execute_json("run", core=str(other), tier="quick", out=str(tmp_path / "baseA"), no_cache=True)
    verdict = execute_json("gate", core=str(fake.config), base="latest", no_cache=True)
    assert verdict["gate"]["base"]["path"] == str(base)
    assert verdict["verdict"] == "reject"
    assert len(verdict["new_failures"]) == 1
    assert not verdict["still_failing"]


def test_compare_latest_uses_requested_core(fake, rvw, tmp_path):
    base, cand, other = (tmp_path / n for n in ("base", "cand", "other"))
    for path, core in ((base, "fake"), (cand, "fake"), (other, "coreA")):
        save_results(_results(core), path)
    for path, core in ((cand, "fake"), (other, "coreA")):
        append_index({"core": core, "run_id": path.name, "path": str(path)})
    code, _, verdict = rvw("regress", "compare", base, "latest", "--core", fake.config, "--json")
    assert code == 0 and verdict["verdict"] == "accept"
    assert verdict["candidate"]["paths"] == [str(cand)]


def test_compare_mcp_cannot_accept_foreign_baseline(fake, tmp_path):
    from rvw.mcp.registry import Registry

    base, cand = tmp_path / "base", tmp_path / "cand"
    save_results(_results("coreA"), base)
    save_results(_results("coreB"), cand)
    registry, errors = Registry.discover({"regress"})
    assert not errors
    _, data, error = registry.call_json("regress_compare", {"base": str(base), "candidate": str(cand)})
    assert error and "core" in data["error"]


def test_gate_binds_latest_candidate_before_running_base(fake, tmp_path):
    from rvw.regress.source import describe

    good = describe(fake.repo).rev
    fake.commit({"rv64ui-p-add": "status=fail fail_code=7"}, msg="broken candidate")
    cand = tmp_path / "candidate"
    execute_json("run", core=str(fake.config), tier="quick", out=str(cand), no_cache=True)
    verdict = execute_json("gate", core=str(fake.config), base_rev=good, cand="latest", no_cache=True)
    assert verdict["gate"]["candidate"]["path"] == str(cand)
    assert verdict["verdict"] == "reject"
    assert len(verdict["new_failures"]) == 1
