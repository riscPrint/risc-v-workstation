"""Incomplete source identities must not let old shards hide a new failure."""
import pytest

from rvw.regress.compare import compare
from rvw.results import SuiteResults, TestEntry, save_results


def _shard(path, seed, status, marker):
    r = SuiteResults("run", "isa", "fixture", "small", "now",
                     source={"core_rev": "same", marker: False},
                     tests=[TestEntry("test", status, seed=seed,
                                      signature="fail:7" if status == "fail" else None,
                                      extra={"elf_sha256": "a" * 64, "options": {}})])
    save_results(r, path)
    return r


@pytest.mark.parametrize("marker", ["identity_complete", "core_identity_covered"])
@pytest.mark.parametrize("side", ["base", "candidate"])
@pytest.mark.parametrize("policy", ["auto", "count"])
def test_incomplete_shards_cannot_hide_new_failure(tmp_path, marker, side, policy):
    first = _shard(tmp_path / "base" / "current", 1, "pass", marker)
    old = _shard(tmp_path / "base" / "old", 2, "fail", marker)
    cand = [_shard(tmp_path / "cand" / str(s), s, "fail", marker) for s in (1, 2)]
    assert compare([first], [cand[0]]).verdict == "reject"
    if side == "base":
        cand[0].tests.extend(cand[1].tests)
    sides = ([first, old], [cand[0]]) if side == "base" else ([first], cand)
    v = compare(*sides, seed_policy=policy)
    assert v.verdict == "inconclusive"
    assert any(side in reason and "identity" in reason for reason in v.reasons)
    assert not v.extra.get("still_failing")


def test_incomplete_pool_cli_gate_and_mcp(fake, rvw, tmp_path):
    from rvw.mcp.registry import Registry

    base, cand = tmp_path / "base", tmp_path / "cand"
    for s, status in ((1, "pass"), (2, "fail")):
        for path, outcome in ((base, status), (cand, "fail")):
            res = _shard(path / str(s), s, outcome, "identity_complete")
            res.core = "fake"  # Match the core requested by gate below.
            save_results(res, res.path)
    code, _, data = rvw("regress", "compare", base, cand, "--json")
    assert code == 3 and data["verdict"] == "inconclusive"
    code, _, data = rvw("regress", "gate", "--core", fake.config, "--base", base,
                        "--cand", cand, "--json")
    assert code == 3 and data["verdict"] == "inconclusive"
    registry, errors = Registry.discover({"regress"})
    assert not errors
    _, data, error = registry.call_json("regress_compare", {"base": str(base), "candidate": str(cand)})
    assert not error and data["verdict"] == "inconclusive"
