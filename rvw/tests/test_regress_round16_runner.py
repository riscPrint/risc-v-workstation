"""Explicit revisions use separate checkouts and old identity keys cannot be reused."""
from regress_fixtures import legacy_layout
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from rvw.regress.config import load_config
from rvw.regress.plan import source_for, suites_plan
from rvw.regress.runner import RunOptions, Runner
from rvw.regress.source import describe
from rvw.results import find_results, load_run


HERE = Path(__file__).resolve().parent


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _runner(fake, out):
    core = load_config(str(fake.config))
    return Runner(core, describe(fake.repo), out, RunOptions(index=False, log=None)), suites_plan(core, ["isa"], None)


def test_explicit_head_revision_uses_a_separate_checkout(fake):
    core = load_config(str(fake.config))
    rev = describe(fake.repo).rev
    src = source_for(core, rev)
    assert src.path != fake.repo and src.rev == rev
    fake.commit({"rv64ui-p-add": "status=fail"}, msg="editor changed HEAD")
    assert describe(src.path).rev == rev


@pytest.mark.parametrize("reuse", ["resume", "cache"])
def test_results_from_before_lock_validation_are_not_reused(fake, tmp_path, reuse):
    from rvw.results import save_run
    out = tmp_path / "old"
    r, plan = _runner(fake, out)
    assert r.run(plan)["ok"]
    legacy_layout(out)
    for pointer in list(r.cache.dir.rglob("current")):
        legacy_layout(pointer.parent)
    for result in find_results(out):
        for entry in result.tests:
            path = result.path / entry.run
            meta_path = path.with_name(".rvw-job.json")
            meta = json.loads(meta_path.read_text())
            # Emulate the old identity and a poisoned pass left by the old runner.
            current = r.cache.get(meta["key"])
            if current is not None:  # equal ELF contents can share a cache key
                shutil.rmtree(current)
            meta["params"].pop("runner_identity_version", None)
            meta["key"] = hashlib.sha256(json.dumps(meta["params"], sort_keys=True).encode()).hexdigest()
            meta_path.write_text(json.dumps(meta))
            old = load_run(path)
            old.cycles = 123456
            save_run(old, path.parent)
            r.cache.put(meta["key"], path.parent)
    fake.reset_calls()
    new, plan = _runner(fake, out if reuse == "resume" else tmp_path / "new")
    assert new.run(plan)["ok"]
    assert len(fake.calls("run")) == 3
    assert all(t.cycles != 123456 for res in find_results(new.out) for t in res.tests)
