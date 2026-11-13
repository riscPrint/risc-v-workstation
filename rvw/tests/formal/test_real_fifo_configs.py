"""The RAM refinement example must preserve its explicit stream observation."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[3]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'examples/formal/equiv-real' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fifo_recipe_preserves_stream_contract(tmp_path, monkeypatch):
    recipe = load('fifo_recipe', 'prepare-fifo.py')
    for role in ('AUTHOR', 'COMMITTER'):
        monkeypatch.setenv(f'GIT_{role}_NAME', 'Test')
        monkeypatch.setenv(f'GIT_{role}_EMAIL', 'test@example.org')
    cases = recipe.prepare(tmp_path / 'cases', ROOT)
    case = cases['fifo']
    repo = Path(case['project']).parent
    gold = recipe.git(repo, 'show', case['gold'] + ':src/main/scala/Export.scala')
    gate = recipe.git(repo, 'show', case['gate'] + ':src/main/scala/Export.scala')
    assert gate == gold.replace('useVec=false', 'useVec=true')
    assert 'new StreamFifo(Bits(8 bits),4,withAsyncRead=true' in gold
    assert 'Mux(fifo.io.pop.valid, fifo.io.pop.payload, B(0,8 bits))' in gold
    assert 'resetKind=SYNC' in gold
    assert recipe.git(repo, 'status', '--porcelain') == ''
    assert 'lock="vex-equiv"' in Path(case['project']).read_text()
    assert "'sbt-equiv'" in (tmp_path / 'cases/generator/build.py').read_text()
    with pytest.raises(FileExistsError):
        recipe.prepare(tmp_path / 'cases', ROOT)


@pytest.mark.parametrize('memory_map', [False, True])
def test_revision_runner_forwards_memory_request(tmp_path, monkeypatch, memory_map):
    runner = load('fifo_runner', 'run.py')
    cases = tmp_path / 'cases.json'
    cases.write_text(json.dumps({'fifo': {'project': 'project.toml', 'gold': 'abc',
                                         'gate': 'def', 'top': 'MemoryFifo'}}))
    def execute(command, **kwargs):
        assert ('--memory-map' in command) == memory_map
        proof = Path(command[command.index('--out') + 1])
        proof.mkdir()
        (proof / 'result.json').write_text('{"status":"inconclusive"}')
        return SimpleNamespace(stdout='', stderr='', returncode=3)
    monkeypatch.setattr(runner.subprocess, 'run', execute)
    records = runner.run(cases, tmp_path / 'proofs', memory_map=memory_map)
    assert records[0]['status'] == 'inconclusive'
