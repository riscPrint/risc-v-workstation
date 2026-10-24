"""Recorded adapter identities bind source claims and declared dependencies."""
import json

from test_regress_adapter_capture import prepared
from rvw.regress.runner import Runner, RunOptions
from rvw.regress.source import describe
from rvw.results import find_results


def new_runner(first, fake, out):
    return Runner(first.core, describe(fake.repo), out,
                  RunOptions(index=False, log=None, results_root=first.opts.results_root))


def test_identity_reuses_across_independent_runners(fake, tmp_path):
    first, plan = prepared(fake, tmp_path)
    assert first.run(plan)['ok'] and first.cacheable
    runs = len(fake.calls('run'))
    resumed = new_runner(first, fake, first.out)
    assert resumed.run(plan)['ok']
    cached = new_runner(first, fake, tmp_path / 'cached')
    assert cached.run(plan)['ok'] and len(fake.calls('run')) == runs
    assert first.identities == resumed.identities == cached.identities
    assert all(t.extra['cached'] for suite in find_results(cached.out) for t in suite.tests)
    for identity in cached.identities.values():
        assert str(cached.inputs.directory) not in json.dumps(identity)
        assert identity['document']['source'] == cached.source.to_dict()
    assert sorted(suite.suite for suite in find_results(tmp_path)) == ['isa', 'isa']


def test_source_path_claims_use_the_selected_checkout(fake, tmp_path):
    first, plan = prepared(fake, tmp_path,
        corrupt="document['result_claims']['source.core_repo'] = document['source']['core_repo']")
    assert first.run(plan)['ok']
    count = len(fake.calls('run'))
    for out in (first.out, tmp_path / 'cached'):
        again = new_runner(first, fake, out)
        assert again.run(plan)['ok'] and len(fake.calls('run')) == count
        for identity in again.identities.values():
            assert identity['document']['result_claims']['source.core_repo'] == str(fake.repo)


def test_changed_declared_dependency_invalidates_resume_and_cache(fake, tmp_path):
    first, plan = prepared(fake, tmp_path)
    policy = tmp_path / 'policy'
    policy.write_text('first policy')
    first.core.cache_paths.append(policy)
    first.close()
    first = new_runner(first, fake, first.out)
    assert first.run(plan)['ok']
    runs = len(fake.calls('run'))
    policy.write_text('new policy')
    changed = new_runner(first, fake, first.out)
    assert changed.tools_key != first.tools_key
    assert changed.run(plan)['ok']
    assert len(fake.calls('run')) == runs + 3
    fresh = new_runner(first, fake, tmp_path / 'cached')
    assert fresh.run(plan)['ok']
    assert all(t.extra['cached'] for suite in find_results(fresh.out) for t in suite.tests)
