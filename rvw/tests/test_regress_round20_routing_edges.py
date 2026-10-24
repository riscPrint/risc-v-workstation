"""Option paths keep their spelling and bind files from the selected working directory."""
from test_regress_round20_options import configured
from race_injection import race_injector
from rvw.regress.plan import suites_plan
from rvw.regress.runner import Runner, RunOptions
from rvw.regress.source import describe
from rvw.results import find_results


def test_relative_undeclared_file_with_spaces_refuses(fake, tmp_path, monkeypatch):
    core, policy = configured(fake, tmp_path, monkeypatch, declared=False)
    policy = policy.rename(tmp_path / 'policy file')
    monkeypatch.chdir(tmp_path)
    core.suite('isa').options = {'policy': policy.name}
    runner = Runner(core, describe(fake.repo), tmp_path / 'out', RunOptions(index=False, log=None))
    summary = runner.run(suites_plan(core, ['isa'], None))
    assert summary['inconclusive'] == 3 and not fake.calls('run')


def test_relative_option_resolution_is_bound_to_cache_identity(fake, tmp_path, monkeypatch):
    core, policy = configured(fake, tmp_path, monkeypatch)
    policy.write_text('pass')
    other = tmp_path / 'alternate'
    other.mkdir()
    (other / 'policy').write_text('fail')
    core.cache_paths.append(other / 'policy')
    core.suite('isa').options = {'policy': 'policy'}
    plan = suites_plan(core, ['isa'], None)

    def runner(name):
        return Runner(core, describe(fake.repo), tmp_path / name, RunOptions(index=False, log=None))

    monkeypatch.chdir(tmp_path)
    assert runner('first').run(plan)['ok']
    monkeypatch.chdir(other)
    second = runner('second').run(plan)
    assert not second['ok'] and second['counts'] == {'fail': 3}
    results = find_results(tmp_path / 'second')
    assert all(test.extra['options']['policy'] == 'policy'
               for suite in results for test in suite.tests)
    assert all(str(other / 'policy') in suite.extra['option_inputs'] for suite in results)


def test_relative_paths_keep_the_captured_working_directory(fake, tmp_path, monkeypatch, race_injector):
    core, policy = configured(fake, tmp_path, monkeypatch)
    policy.write_text('fail')
    other = tmp_path / 'alternate'
    other.mkdir()
    (other / 'policy').write_text('pass')
    core.cache_paths.append(other / 'policy')
    core.suite('isa').options = {'policy': 'policy'}
    monkeypatch.chdir(tmp_path)
    runner = Runner(core, describe(fake.repo), tmp_path / 'out', RunOptions(index=False, log=None))
    race = race_injector.at(runner, '_run_tests', lambda: monkeypatch.chdir(other),
                            when='before', restore=lambda: monkeypatch.chdir(tmp_path))
    result = runner.run(suites_plan(core, ['isa'], None))
    assert race.fired and not result['ok'] and result['counts'] == {'fail': 3}
