"""The real-source recipe must isolate its inputs and commit both revisions."""
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('real_equiv_prepare', ROOT/'examples/formal/equiv-real/prepare.py')
recipe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recipe)


def test_private_revision_recipe(tmp_path, monkeypatch):
    original = recipe.git
    divider = '''package spinal.lib.math
  val done = RegInit(True)
  val waitRsp = RegInit(False)
  done := !io.cmd.valid
  waitRsp := True
    remainder := remainderShifted.resized
    numerator := (numerator ## !remainderMinusDenominator.msb).asUInt.resized
    when(!remainderMinusDenominator.msb){
      remainder := remainderMinusDenominator.resized
    }
'''
    def git(root, *args):
        if root in (tmp_path/'spinal', tmp_path/'vex'):
            if args[0] == 'rev-parse':
                return 'a'*40
            return divider if root.name == 'spinal' else 'package vexriscv.ip.fpu'
        return original(root,*args)
    monkeypatch.setattr(recipe,'git',git)
    # Git identity is local to the test process.
    monkeypatch.setenv('GIT_AUTHOR_NAME','Test')
    monkeypatch.setenv('GIT_COMMITTER_NAME','Test')
    monkeypatch.setenv('GIT_AUTHOR_EMAIL','test@example.org')
    monkeypatch.setenv('GIT_COMMITTER_EMAIL','test@example.org')
    cases = recipe.prepare(tmp_path/'private',tmp_path/'spinal',tmp_path/'vex',ROOT)
    for name, case in cases.items():
        repo = Path(case['project']).parent
        assert case['gold'] != case['gate']
        assert original(repo,'status','--porcelain') == ''
        project = Path(case['project']).read_text()
        assert 'lock="vex-equiv"' in project
        assert 'source_env="EQUIV_SOURCE"' in project
        assert original(repo,'show',case['gold']+':provenance.json')
    repo = tmp_path/'private/divider'
    before = original(repo,'show',cases['divider']['gold']+':src/main/scala/Unit.scala')
    after = original(repo,'show',cases['divider']['gate']+':src/main/scala/Unit.scala')
    assert 'when(!remainderMinusDenominator.msb)' in before
    assert 'val stateCode = Reg(Bits(3 bits))' in after
    assert 'doneNext := !io.cmd.valid' in after
    assert 'waitRspNext := True' in after
    assert "'sbt-equiv'" in (tmp_path/'private/generator/build.py').read_text()
    sqrt = tmp_path/'private/sqrt'
    assert original(sqrt,'show',cases['sqrt']['gold']+':src/main/scala/Unit.scala') == original(sqrt,'show',cases['sqrt']['gate']+':src/main/scala/Unit.scala')
    assert 'oneFilePerComponent=true' in (sqrt/'src/main/scala/RealExport.scala').read_text()
    assert json.loads((tmp_path/'private/cases.json').read_text()) == cases
