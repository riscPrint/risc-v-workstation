"""Declared stimulus paths retain their identity in options and environment."""
import json
from pathlib import Path

import pytest

from rvw.regress.config import load_config
from rvw.regress.plan import suites_plan
from rvw.regress.runner import Runner, RunOptions
from rvw.regress.source import describe
from rvw.results import find_results, load_run


def configured(fake, tmp_path, monkeypatch, *, channel='option', spelling='absolute', declared=True):
    policy = tmp_path / 'policy'
    policy.write_text('fail')
    name = str(policy)
    if spelling == 'relative':
        monkeypatch.chdir(tmp_path)
        name = './policy'
    elif spelling == 'parent':
        name = str(tmp_path / 'subdir/../policy')
    core = load_config(str(fake.config))
    core.cache_paths = [policy] if declared else []
    adapter = tmp_path / 'policy_adapter.py'
    text = Path(core.adapter[1]).read_text()
    if channel == 'option':
        core.suite('isa').options = {'policy': name}
        read = "Path(job['policy']).read_text()"
        echo = "res['options'] = {'policy': job['policy']}"
    elif channel == 'nested':
        core.suite('isa').options = {'policy': {'files': [name]}}
        read = "Path(job['policy']['files'][0]).read_text()"
        echo = "res['options'] = {'policy': job['policy']}"
    elif channel == 'env':
        monkeypatch.setenv('POLICY_FLAGS', '--policy=' + name)
        core.input_env.append('POLICY_FLAGS')
        read = "Path(os.environ['POLICY_FLAGS'].split('=', 1)[1]).read_text()"
        echo = 'pass'
    else:
        core.suite('elab').build_options = ['--policy=' + name]
        text = text.replace('b.add_argument("--json", action="store_true")',
                            'b.add_argument("--json", action="store_true")\n    b.add_argument("--policy")')
        text = text.replace('if a.json:', "if Path(a.policy).read_text() == 'fail':\n            return 1\n        if a.json:")
        read, echo = "'pass'", 'pass'
    text = text.replace('d = directives(elf)', "d = directives(elf)\n    d['status'] = " + read + "\n    d['fail_code'] = '7'")
    text = text.replace('if metrics:', echo + '\n    if metrics:')
    adapter.write_text(text)
    core.adapter[1] = str(adapter)
    return core, policy


@pytest.mark.parametrize('spelling', ['absolute', 'relative', 'parent'])
@pytest.mark.parametrize('declared', [False, True])
def test_option_paths_must_be_declared(fake, tmp_path, monkeypatch, spelling, declared):
    core, policy = configured(fake, tmp_path, monkeypatch, spelling=spelling, declared=declared)
    runner = Runner(core, describe(fake.repo), tmp_path / 'out', RunOptions(index=False, log=None))
    summary = runner.run(suites_plan(core, ['isa'], None))
    if not declared or spelling == 'parent':
        assert summary['inconclusive'] == 3 and not fake.calls('run')
    else:
        assert summary['counts'] == {'fail': 3} and summary['inconclusive'] == 0


def test_declared_options_keep_identity_and_reuse(fake, tmp_path, monkeypatch):
    core, policy = configured(fake, tmp_path, monkeypatch)
    policy.write_text('pass')
    plan = suites_plan(core, ['isa'], None)

    def runner(out):
        return Runner(core, describe(fake.repo), out, RunOptions(index=False, log=None))

    first = runner(tmp_path / 'out')
    assert first.run(plan)['ok']
    count = len(fake.calls('run'))
    assert runner(first.out).run(plan)['ok']
    assert runner(tmp_path / 'cached').run(plan)['ok']
    assert len(fake.calls('run')) == count
    for suite in find_results(tmp_path / 'cached'):
        for test in suite.tests:
            assert test.extra['cached']
            assert test.extra['options']['policy'] == str(policy)
            assert load_run(suite.path / test.run).extra['options']['policy'] == str(policy)


@pytest.mark.parametrize('suffix', ['/missing', '/../policy'])
def test_uncaptured_tree_member_refuses_before_execution(fake, tmp_path, suffix):
    core = load_config(str(fake.config))
    core.suite('isa').options = {'policy': str(fake.repo) + suffix}
    runner = Runner(core, describe(fake.repo), tmp_path / 'out', RunOptions(index=False, log=None))
    summary = runner.run(suites_plan(core, ['isa'], None))
    assert summary['inconclusive'] == 3 and not fake.calls('run')


def test_environment_keeps_declared_paths(fake, tmp_path, monkeypatch):
    core, policy = configured(fake, tmp_path, monkeypatch, channel='env')
    second = tmp_path / 'second policy'
    second.write_text('data')
    core.cache_paths.append(second)
    core.input_env.append('INPUT_LIST')
    value = str(policy) + ':' + str(second) + ':' + str(policy)
    monkeypatch.setenv('INPUT_LIST', value)
    runner = Runner(core, describe(fake.repo), tmp_path / 'out', RunOptions(index=False, log=None))
    expected = value
    assert runner.env['INPUT_LIST'] == expected
    runner.capture_plan(suites_plan(core, ['isa'], None))
    assert runner.env['INPUT_LIST'] == expected
    assert runner.inputs.record()['env']['INPUT_LIST'] == value
