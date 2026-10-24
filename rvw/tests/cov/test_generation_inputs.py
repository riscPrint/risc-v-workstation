"""Coverage must consume the published generation, including each artifact."""
import json
from pathlib import Path

import pytest
from race_injection import race_injector
from rvw.cov import code
from rvw.results.generation import GenerationError, open_current, publish
from .test_code import dat


@pytest.fixture
def store(tmp_path):
    root = tmp_path / 'out'
    source = {'core_rev': 'a' * 40, 'core_dirty': False}
    def build(directory, count=0):
        suite = directory / 'isa/small'
        (suite / 'A').mkdir(parents=True)
        (directory / 'run.json').write_text(json.dumps({
            'schema': 'rvw.regress-run/1', 'run_id': 'r', 'core': 'test', 'finished': 'now',
            'source': source, 'results': [{'path': 'isa/small', 'suite': 'isa', 'config': 'small', 'tests': 1}]}))
        (suite / 'results.json').write_text(json.dumps({
            'schema': 'rvw.results/1', 'run_id': 'r', 'suite': 'isa', 'core': 'test',
            'config': 'small', 'created': 'now', 'source': source, 'run_set': '../..',
            'tests': [{'id': 'A', 'status': 'pass', 'run': 'A/result.json'}]}))
        (suite / 'A/result.json').write_text(json.dumps({
            'schema': 'rvw.run/1', 'status': 'pass', 'core': 'test', 'elf': 'program.elf',
            'config': 'small', 'source': source, 'artifacts': {'coverage': 'coverage.dat'}}))
        dat(suite / 'A/coverage.dat', [count])
    build(root, 1)  # A resume workspace can differ from its publication.
    publish(root, build)
    return root, build


@pytest.mark.parametrize('member', ['.', 'isa/small', 'isa/small/results.json',
                                    'isa/small/A', 'isa/small/A/result.json'])
@pytest.mark.parametrize('revert', [False, True])
def test_generation_pins_all_coverage_inputs(store, tmp_path, race_injector, member, revert):
    root, build = store
    old = open_current(root)
    pointer = (root / 'current').read_bytes()
    publish(root, lambda directory: build(directory, 7))
    next_pointer = (root / 'current').read_bytes()
    (root / 'current').chmod(0o644)
    (root / 'current').write_bytes(pointer)
    # A resume publishes after dispatch but before parsing its coverage.
    race = race_injector.file(code, 'iter_dat', root / 'current', next_pointer,
                              replace=True, revert=revert)
    result = code.merge([str(root / member)], tmp_path)
    assert race.fired
    assert result['points'][0]['count'] == 0
    assert next(iter(result['tests'].values()))['generation'] == old.id
    assert old.id in result['generations']


@pytest.mark.parametrize('revert', [False, True])
def test_changed_published_coverage_refuses(store, tmp_path, race_injector, revert):
    root, _ = store
    generation = open_current(root)
    artifact = generation.path / 'isa/small/A/coverage.dat'
    artifact.chmod(0o644)
    artifact.parent.chmod(0o755)
    # Change after open_current's full validation, before the artifact capture.
    race = race_injector.file(code, '_run_input', artifact,
                              artifact.read_bytes().replace(b"' 0", b"' 1"),
                              replace=True, revert=revert)
    with pytest.raises(GenerationError, match='generation artifact changed'):
        code.merge([str(root / 'isa/small')], tmp_path)
    assert race.fired


def test_cli_and_mcp_use_published_coverage(store, tmp_path, rvw):
    from rvw.cov.cli import execute_json
    root, _ = store
    status, _, cli = rvw('cov', 'merge', root / 'isa/small', '--source-root', tmp_path, '--json')
    mcp = execute_json('merge', inputs=[str(root / 'isa/small')], source_root=str(tmp_path))
    assert status == 0
    assert cli['points'][0]['count'] == mcp['points'][0]['count'] == 0
    assert cli['generations'] == mcp['generations']


def test_explicit_old_generation_keeps_its_id(store, tmp_path):
    root, build = store
    old = open_current(root)
    publish(root, lambda directory: build(directory, 7))
    result = code.merge([str(old.path / 'isa/small')], tmp_path)
    assert result['points'][0]['count'] == 0
    assert result['generations'] == [old.id]
