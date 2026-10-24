"""Captured ELF names and published result generations."""
import json
import shutil
from pathlib import Path

import pytest

from race_injection import race_injector
from rvw.regress.config import load_config
from rvw.regress.plan import suites_plan
from rvw.regress.runner import Runner, RunOptions
from rvw.regress.source import describe
from rvw.results import find_results, load_run, load_results, SchemaError
from rvw.regress.compare import compare
from rvw.results.generation import open_current, publish

HERE = Path(__file__).parent


def setup_runner(fake, out, *, adapter=None, deps=()):
    core = load_config(str(fake.config))
    core.input_complete = True
    core.input_env = ['FAKE_ADAPTER_LOG', 'FAKE_TOOLCHAIN', 'PYTHONPATH']
    core.input_tools = []
    if adapter:
        core.adapter[1] = str(adapter)
    core.cache_paths = list(deps)
    return Runner(core, describe(fake.repo), out, RunOptions(log=None, index=False)), suites_plan(core, ['isa'], None)


@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
def test_reader_pins_one_generation(fake, tmp_path, race_injector, replace, revert):
    out = tmp_path / 'out'
    runner, plan = setup_runner(fake, out)
    runner.run(plan)
    old = open_current(out)
    import rvw.results.schema as schema

    old_pointer = (out / 'current').read_bytes()
    def build(directory):
        for child in old.path.iterdir():
            if child.name == 'generation.json':
                continue
            if child.is_dir():
                shutil.copytree(child, directory / child.name)
            else:
                shutil.copyfile(child, directory / child.name)
        path = directory / 'isa/small/results.json'
        data = json.loads(path.read_text())
        data['tests'][0].update(status='fail', signature='fail:7')
        path.chmod(0o644)
        path.write_text(json.dumps(data))
    publish(out, build)
    new_pointer = (out / 'current').read_bytes()
    (out / 'current').chmod(0o644)
    (out / 'current').write_bytes(old_pointer)
    race = race_injector.file(schema, '_read_results', out / 'current', new_pointer,
                              replace=replace, revert=revert)
    pinned = find_results(out)
    assert race.fired and pinned[0].generation == old.id
    assert all(t.status == 'pass' for t in pinned[0].tests)
    if revert:
        assert open_current(out).id == old.id
        (out / 'current').write_bytes(new_pointer)
    assert open_current(out).id != old.id
    verdict = compare(pinned, pinned)
    assert verdict.verdict == 'accept'
    assert verdict.extra['generations'] == {'base': [old.id], 'head': [old.id]}
    assert find_results(out)[0].tests[0].status == 'fail'


def test_missing_declaration_is_inconclusive(fake, tmp_path):
    core = load_config(str(fake.config))
    core.input_complete = False
    runner = Runner(core, describe(fake.repo), tmp_path / 'out', RunOptions(log=None, index=False))
    summary = runner.run(suites_plan(core, ['isa'], None))
    assert not summary['ok'] and summary['inconclusive'] == 3
    assert not fake.calls('run')
    assert not list(runner.cache.dir.rglob('result.json'))


def test_nested_reader_uses_published_generation(fake, tmp_path):
    out = tmp_path / 'out'
    runner, plan = setup_runner(fake, out)
    runner.run(plan)
    generation = open_current(out)
    # Mutable resume workspace is not claim-bearing evidence.
    (out / 'isa/small/results.json').write_text('{}')
    assert load_results(out / 'isa/small').generation == generation.id
    (generation.path / 'isa/small/results.json').chmod(0o644)
    (generation.path / 'isa/small/results.json').write_text('{}')
    with pytest.raises(SchemaError, match='changed'):
        find_results(out)


def test_selected_elf_name_prevents_cache_collision(fake, tmp_path):
    # The fake adapter uses ELF names for core overrides. Equal bytes are not equal path inputs.
    fake.prog('rv64ui-p-add', 'status=pass')
    fake.prog('rv64ui-p-sub', 'status=pass')
    fake.commit({'rv64ui-p-sub': 'status=fail fail_code=9'}, msg='one name fails')
    runner, plan = setup_runner(fake, tmp_path / 'first')
    assert not runner.run(plan)['ok']
    again, plan = setup_runner(fake, tmp_path / 'second')
    assert not again.run(plan)['ok']
    results = find_results(again.out)
    assert next(t for t in results[0].tests if t.id == 'rv64ui-p-sub').status == 'fail'


def test_missing_current_never_reads_workspace(fake, tmp_path):
    runner, plan = setup_runner(fake, tmp_path / 'out')
    runner.run(plan)
    (runner.out / 'current').unlink()
    with pytest.raises(SchemaError, match='current is missing'):
        find_results(runner.out)
