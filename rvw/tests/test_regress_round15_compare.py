"""A comparison must not pool ambiguous sources or duplicate samples."""
import pytest

# ------------------------------------------------------------------------------ comparison

from rvw.regress.compare import compare
from rvw.results import SuiteResults, TestEntry, save_results


def _result(path, rev="base", seed=1, status="pass", cycles=100, perf=False, **source_fields):
    r = SuiteResults("run", "isa", "fixture", "small", "now",
                     source={"core_rev": rev, "core_dirty": False, **source_fields},
                     tests=[TestEntry("test", status, seed=seed, cycles=cycles,
                                      signature="fail:7" if status == "fail" else None,
                                      run=f"tests/seed-{seed}/result.json",
                                      extra={"elf_sha256": "a" * 64, "options": {},
                                             "metric_origins": {"cycles": "cycles"}})],
                     extra={"perf_metrics": ["cycles"]} if perf else {})
    save_results(r, path)
    return r


@pytest.mark.parametrize("side", ["base", "candidate"])
@pytest.mark.parametrize("field,value", [("core_rev", "old"), ("core_fingerprint", "other"),
                                         ("core_links", "other"), ("core_rev_full", "other-full"),
                                         ("tools_key", "other-tools"), ("core", "other-core")])
def test_compare_refuses_mixed_source_trees(tmp_path, side, field, value):
    base = _result(tmp_path / "base", status="pass")
    candidate = _result(tmp_path / "candidate", rev="candidate", status="fail")
    mixed = _result(tmp_path / "mixed", rev=base.source["core_rev"] if side == "base" else "candidate",
                    seed=2, status="fail")
    if field == "core":
        mixed.core = value
    else:
        mixed.source[field] = value
    sides = ([base, mixed], [candidate]) if side == "base" else ([base], [candidate, mixed])
    with pytest.raises(ValueError, match=f"{side}.*source identity"):
        compare(*sides)


@pytest.mark.parametrize("side", ["base", "candidate"])
@pytest.mark.parametrize("split", [False, True])
@pytest.mark.parametrize("seed", [None, 1])
def test_compare_refuses_duplicate_test_seed(tmp_path, side, split, seed):
    base = _result(tmp_path / "base", seed=seed, perf=True)
    candidate = _result(tmp_path / "candidate", rev="candidate", seed=seed, cycles=120, perf=True)
    target = base if side == "base" else candidate
    duplicate = _result(tmp_path / "duplicate", rev=target.source["core_rev"], seed=seed, cycles=80, perf=True)
    if split:
        sides = ([base, duplicate], [candidate]) if side == "base" else ([base], [candidate, duplicate])
    else:
        target.tests.extend(duplicate.tests)
        sides = ([base], [candidate])
    with pytest.raises(ValueError, match=f"{side}.*duplicate.*seed"):
        compare(*sides)


def test_compare_tree_cannot_hide_failure_or_slowdown(tmp_path):
    base = _result(tmp_path / "base" / "current")
    _result(tmp_path / "base" / "old", rev="old", status="fail")
    candidate = _result(tmp_path / "candidate", rev="candidate", status="fail")
    assert compare([base], [candidate]).verdict == "reject"
    with pytest.raises(ValueError, match="base.*source identity"):
        compare(tmp_path / "base", tmp_path / "candidate")
    _result(tmp_path / "perf-base", perf=True)
    _result(tmp_path / "perf-candidate" / "current", rev="candidate", perf=True, cycles=120)
    _result(tmp_path / "perf-candidate" / "stale", rev="candidate", perf=True, cycles=80)
    assert compare(tmp_path / "perf-base", tmp_path / "perf-candidate" / "current").verdict == "reject"
    with pytest.raises(ValueError, match="candidate.*duplicate"):
        compare(tmp_path / "perf-base", tmp_path / "perf-candidate")


def test_compare_preserves_owner_of_each_seed(tmp_path):
    base = _result(tmp_path / "base")
    first = _result(tmp_path / "candidate" / "first", rev="candidate", status="fail")
    second = _result(tmp_path / "candidate" / "second", rev="candidate", seed=2)
    v = compare([base], [first, second])
    assert v.verdict == "reject"
    assert v.new_failures[0]["run"] == str(first.path / first.tests[0].run)
    failed_base = _result(tmp_path / "failed-base" / "first", status="fail")
    passing_base = _result(tmp_path / "failed-base" / "second", seed=2)
    fixed = compare([failed_base, passing_base], [_result(tmp_path / "fixed")])
    assert fixed.fixed[0]["run"] == str(failed_base.path / failed_base.tests[0].run)


def test_runner_c3_preserves_dirty_source_identity(fake, rvw, tmp_path):
    from rvw.results import find_results
    paths = []
    for edit in ("first", "second"):
        (fake.repo / "counter").write_text(edit)
        out = tmp_path / edit
        code, _, data = rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", out,
                            "--no-cache", "--no-index", "--json")
        assert code == 0
        paths.append(out)
        r = find_results(out)[0]
        assert r.source["core_rev_full"] == data["source"]["core_rev_full"]
        assert r.source["core_fingerprint"] == data["source"]["core_fingerprint"]
        assert r.source["adapter"] == data["source"]["adapter"]
    # The same revision and dirty=True do not make two edits the same source.
    with pytest.raises(ValueError, match="base.*source identity"):
        compare([*find_results(paths[0]), *find_results(paths[1])], find_results(paths[1]))


def _manifest(path, full_rev):
    import json
    r = _result(path / "isa" / "small", rev="aaaaaaa", seed=1 if path.name == "first" else 2)
    (path / "run.json").write_text(json.dumps({
        "schema": "rvw.regress-run/1", "run_id": r.run_id, "finished": "now",
        "source": {**r.source, "core_rev_full": full_rev},
        "results": [{"suite": r.suite, "config": r.config, "path": "isa/small", "tests": len(r.tests)}]}))
    return r


def test_compare_uses_full_manifest_identity_for_older_c3(tmp_path):
    _manifest(tmp_path / "tree" / "first", "a" * 40)
    _manifest(tmp_path / "tree" / "second", "a" * 7 + "b" * 33)
    candidate = _result(tmp_path / "candidate")
    with pytest.raises(ValueError, match="base.*source identity"):
        compare(tmp_path / "tree", [candidate])


def test_run_set_refuses_conflicting_full_source_identity(tmp_path):
    from rvw.results import find_results, SchemaError
    r = _manifest(tmp_path / "first", "a" * 40)
    r.source["core_rev_full"] = "a" * 7 + "b" * 33
    save_results(r, r.path)
    with pytest.raises(SchemaError, match="core_rev_full"):
        find_results(tmp_path / "first")


@pytest.mark.parametrize("unknown", [{}, {"core_rev": "base", "core_dirty": True}])
def test_compare_refuses_unknown_shard_identity(tmp_path, unknown):
    first = _result(tmp_path / "first")
    second = _result(tmp_path / "second", seed=2)
    first.source = second.source = unknown
    with pytest.raises(ValueError, match="base.*source identity"):
        compare([first, second], [_result(tmp_path / "candidate")])


@pytest.mark.parametrize("field,value", [("perf_metrics", ["cycles"]), ("seeds", {"mode": "random"})])
def test_compare_refuses_inconsistent_shard_contract(tmp_path, field, value):
    first = _result(tmp_path / "first")
    second = _result(tmp_path / "second", seed=2)
    second.extra[field] = value
    with pytest.raises(ValueError, match="base.*inconsistent.*metrics or seed modes"):
        compare([first, second], [_result(tmp_path / "candidate")])


def test_compare_allows_shards_at_different_checkout_paths(tmp_path):
    first = _result(tmp_path / "first", core_repo="/one/checkout")
    second = _result(tmp_path / "second", seed=2, core_repo="/other/checkout")
    first.source["core_rev_full"] = second.source["core_rev_full"] = "a" * 40
    assert compare([first, second], [first, second]).verdict == "accept"


@pytest.mark.parametrize('side', ['base', 'candidate'])
@pytest.mark.parametrize('field', ['rtl_sha256', 'adapter_identity'])
@pytest.mark.parametrize('other', ['b' * 64, None])
def test_disjoint_seed_shards_refuse_different_model_identity(tmp_path, side, field, other):
    first = _result(tmp_path / 'first', core_rev_full='a' * 40)
    second = _result(tmp_path / 'second', seed=2, core_rev_full='a' * 40)
    for shard in (first, second):
        shard.tests[0].extra.update(rtl_sha256='a' * 64, adapter_identity='a' * 64)
    if other is None:
        second.tests[0].extra.pop(field)
    else:
        second.tests[0].extra[field] = other
    matching = _result(tmp_path / 'matching', core_rev_full='a' * 40)
    sides = ([first, second], [matching]) if side == 'base' else ([matching], [first, second])
    with pytest.raises(ValueError, match=side + '.*more than one design'):
        compare(*sides)


def test_base_and_candidate_can_have_different_model_identities(tmp_path):
    base = [_result(tmp_path / 'base' / str(seed), seed=seed, core_rev_full='a' * 40)
            for seed in (1, 2)]
    candidate = [_result(tmp_path / 'candidate' / str(seed), seed=seed, core_rev_full='b' * 40)
                 for seed in (1, 2)]
    for shards, identity in ((base, 'a' * 64), (candidate, 'b' * 64)):
        for shard in shards:
            shard.tests[0].extra.update(rtl_sha256=identity, adapter_identity=identity)
    assert compare(base, candidate).verdict == 'accept'
