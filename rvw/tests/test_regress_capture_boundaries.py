"""Capture paths and repeated references keep one logical input boundary."""
import json
import os
import shutil
from pathlib import Path

import pytest

from race_injection import race_injector
from rvw.regress import config as config_module
from rvw.regress.config import load_config
from rvw.regress.plan import suites_plan
from rvw.regress.runner import Runner, RunOptions
from rvw.regress.source import describe
from rvw.results import SchemaError, find_results
from rvw.results.generation import open_current, publish


def runner_for(fake, out):
    core = load_config(str(fake.config))
    return Runner(core, describe(fake.repo), out, RunOptions(index=False, log=None)), suites_plan(core, ['isa'], None)


def test_elf_lookup_keeps_symlink_capture(fake, tmp_path):
    target = tmp_path / 'program'
    target.write_text('status=fail fail_code=9')
    lookup = fake.isa / 'rv64ui-p-add'
    lookup.unlink()
    lookup.symlink_to(target)
    runner, plan = runner_for(fake, tmp_path / 'out')
    result = runner.run(plan)
    assert not result['ok'] and result['counts'] == {'pass': 2, 'fail': 1}
    entry = next(item for item in runner.inputs.record()['files'] if item['source'] == str(lookup))
    assert entry['resolved'] == str(target)
    assert {'path': str(lookup), 'target': str(target)} in entry['symlinks']


@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
def test_repeated_result_path_resolves_generation_once(fake, tmp_path, race_injector, replace, revert):
    from rvw.regress import compare as compare_module
    runner, plan = runner_for(fake, tmp_path / 'out')
    runner.run(plan)
    old = open_current(runner.out)
    pointer = runner.out / 'current'
    initial = pointer.read_bytes()

    def build(directory):
        for child in old.path.iterdir():
            if child.name == 'generation.json':
                continue
            if child.is_dir():
                shutil.copytree(child, directory / child.name)
            else:
                shutil.copyfile(child, directory / child.name)
        path = directory / 'isa/small/results.json'
        value = json.loads(path.read_text())
        value['tests'][0].update(status='fail', signature='fail:9')
        path.chmod(0o644)
        path.write_text(json.dumps(value))

    publish(runner.out, build)
    changed = pointer.read_bytes()
    pointer.chmod(0o644)
    pointer.write_bytes(initial)
    race = race_injector.file(compare_module, 'find_results', pointer, changed,
                              when='before' if revert else 'after', replace=replace, revert=revert)
    verdict = compare_module.compare(runner.out, runner.out)
    assert race.fired
    assert verdict.extra['generations']['base'] == verdict.extra['generations']['head']


@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
def test_private_marker_cannot_hide_published_run(fake, tmp_path, race_injector, replace, revert):
    import rvw.results.schema as schema
    runner, plan = runner_for(fake, tmp_path / 'out')
    runner.run(plan)
    marker = runner.out / '.rvw-cache-entry'

    def insert():
        if replace:
            pending = marker.with_suffix('.new')
            pending.write_text('rvw.regress-cache/1\n')
            os.replace(pending, marker)
        else:
            marker.write_text('rvw.regress-cache/1\n')

    race = race_injector.at(schema, 'find_results', insert, when='before',
                            restore=(lambda: marker.unlink()) if revert else None)
    with pytest.raises(SchemaError, match='private.*run set'):
        schema.find_results(tmp_path)
    assert race.fired


@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
def test_gate_cannot_accept_after_any_capture_failure(fake, tmp_path, race_injector, replace, revert):
    from rvw.regress import plan as plan_module
    candidate, plan = runner_for(fake, tmp_path / 'candidate')
    assert candidate.run(plan)['ok']
    text = fake.config.read_text().replace('input_complete = true', 'input_complete = false')
    race = race_injector.file(config_module, 'load_config', fake.config, text.encode(),
                              replace=replace, revert=revert)
    core = config_module.load_config(str(fake.config))
    verdict = plan_module.gate(core, 'quick', describe(fake.repo).rev, None, None, str(candidate.out), None,
                              RunOptions(index=False, log=None, use_cache=False,
                                         results_root=tmp_path / 'results'), None, None)['verdict']
    assert race.fired
    assert verdict.verdict == 'inconclusive'
    assert any('input_not_captured' in reason for reason in verdict.reasons)


@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
def test_c1_path_comes_from_captured_lookup(tmp_path, race_injector, replace, revert):
    import rvw.results.schema as schema
    first, second = tmp_path / 'first', tmp_path / 'second'
    for directory, status in ((first, 'pass'), (second, 'fail')):
        directory.mkdir()
        (directory / 'result.json').write_text(json.dumps({'schema': 'rvw.run/1', 'status': status}))
        (directory / 'run.log').write_text(directory.name)
    alias = tmp_path / 'alias'
    alias.symlink_to(first, target_is_directory=True)

    def retarget(target):
        if replace:
            pending = tmp_path / 'pending-alias'
            pending.symlink_to(target, target_is_directory=True)
            os.replace(pending, alias)
        else:
            alias.unlink()
            alias.symlink_to(target, target_is_directory=True)

    command = race_injector.at(schema, 'load_run', lambda: None, when='before',
                              restore=(lambda: retarget(first)) if revert else None)
    race = race_injector.at(schema, '_read_json', lambda: retarget(second), when='after')
    result = schema.load_run(alias)
    assert command.fired and race.fired
    assert result.status == 'pass' and result.path == first
    assert result.artifact('log').read_text() == 'first'
