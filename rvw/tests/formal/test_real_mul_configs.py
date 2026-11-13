"""Capture the real helper source and vary only its hardware split size."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    'mul_configs', ROOT / 'examples/formal/equiv-real/prepare-mul-configs.py')
recipe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recipe)


@pytest.mark.parametrize('marker', ['case class AgedArbiterUp', 'changed boundary'])
def test_configuration_capture(tmp_path, monkeypatch, marker):
    for role in ('AUTHOR', 'COMMITTER'):
        monkeypatch.setenv(f'GIT_{role}_NAME', 'Test')
        monkeypatch.setenv(f'GIT_{role}_EMAIL', 'test@example.org')
    source = tmp_path / 'core'
    path = source / 'src/main/scala/vexiiriscv/misc/Utils.scala'
    path.parent.mkdir(parents=True)
    raw = ('package vexiiriscv.misc\n// helpers\n' + marker + '\n\n').encode()
    path.write_bytes(raw)
    recipe.git(source, 'init', '-q')
    revision = recipe.commit(source, 'test: capture source')
    # The working tree is not the source of the committed recipe.
    path.write_text('dirty source must not be copied')
    out = tmp_path / 'cases'
    if marker != 'case class AgedArbiterUp':
        with pytest.raises(ValueError, match='boundary changed'):
            recipe.prepare(out, source, ROOT)
        assert not out.exists()
        return
    cases = recipe.prepare(out, source, ROOT)
    case = cases['mul']
    repo = out / 'unit'
    provenance = json.loads((repo / 'provenance.json').read_text())
    assert provenance['source_revision'] == revision
    assert provenance['source_sha256'] == hashlib.sha256(raw).hexdigest()
    assert (repo / 'src/main/scala/Utils.scala').read_bytes() == raw.split(marker.encode())[0]
    gold = recipe.git(repo, 'show', case['gold'] + ':src/main/scala/Export.scala')
    gate = recipe.git(repo, 'show', case['gate'] + ':src/main/scala/Export.scala')
    assert gate == gold.replace('MulSpliter(33,33,17,17,true,true)',
                                'MulSpliter(33,33,9,9,true,true)')
    assert 'in Bits(8 bits)' in gold
    assert 'a.asSInt.resize(33).asBits' in gold
    assert 'out Bits(64 bits)' in gold
    assert '_.toMulU(aa,bb,64)' in gold
    assert recipe.git(repo, 'status', '--porcelain') == ''
    assert 'lock="vex-equiv"' in (repo / 'rvw.toml').read_text()
    assert "'sbt-equiv'" in (out / 'generator/build.py').read_text()
    assert json.loads((out / 'cases.json').read_text()) == cases
