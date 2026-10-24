"""Private Git excludes cannot remove source inputs or restore an old pass."""
import json

import pytest

from regress_fixtures import git
from rvw.common.capture import Capture
from rvw.regress.config import load_config
from rvw.regress.plan import suites_plan
from rvw.regress.runner import Runner, RunOptions
from rvw.regress.source import describe
from rvw.results import find_results


@pytest.mark.parametrize('exclude', ['private', 'global'])
def test_private_excludes_cannot_restore_clean_cached_pass(
        fake, tmp_path, exclude):
    core = load_config(str(fake.config))
    plan = suites_plan(core, ['isa'], None)

    def runner(name):
        return Runner(core, describe(fake.repo), tmp_path / name,
                      RunOptions(index=False, log=None))

    assert runner('base').run(plan)['ok']
    rules = fake.repo / '.git/info/exclude' if exclude == 'private' else tmp_path / 'global-ignore'
    rules.write_text('overrides.json\n')
    if exclude == 'global':
        git(fake.repo, 'config', 'core.excludesFile', str(rules))
    source = fake.repo / 'overrides.json'
    source.write_text(json.dumps({'rv64ui-p-add': 'status=fail fail_code=7'}))
    assert describe(fake.repo).dirty
    candidate = runner('candidate')
    summary = candidate.run(plan)
    assert not summary['ok']
    assert candidate.source.dirty and not candidate.cacheable
    tests = [t for suite in find_results(candidate.out) for t in suite.tests]
    assert next(t for t in tests if t.id == 'rv64ui-p-add').status == 'fail'
    assert not any(t.extra.get('cached') for t in tests)


def test_capture_uses_only_repository_ignore_rules(fake, tmp_path):
    (fake.repo / '.gitignore').write_text('build-output\n')
    (fake.repo / 'build-output').write_text('ignored by repository')
    (fake.repo / '.git/info/exclude').write_text('private-source\n')
    (fake.repo / 'private-source').write_text('captured')
    tree = Capture(tmp_path / 'capture').tree(fake.repo)
    assert not (tree.copy / 'build-output').exists()
    assert (tree.copy / 'private-source').read_text() == 'captured'
