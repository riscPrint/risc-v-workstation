"""Wired scaffolds carry one elaboration policy and complete standard inputs."""
import pytest
from rvw.init.scaffold import scaffold
from rvw.regress.config import load_config
pytestmark = pytest.mark.fast


def test_wired_inputs_and_rtl_hooks(tmp_path, monkeypatch):
    monkeypatch.setenv("RVW_HOME", str(tmp_path))
    (tmp_path / 'build.sbt').write_text('val spinalVersion = "1.15.0"\nlazy val cpu = project\n')
    scaffold(tmp_path, isa='rv32i', sbt_project='cpu', db_top='demo.Core')
    config = load_config(project=tmp_path)
    assert config.input_complete and config.identity and config.identity_capture
    text = (tmp_path / 'rvw/src/main/scala/rvwcore/CoreAdapter.scala').read_text()
    assert 'def generatedVerilog(model: Model)' in text
    assert 'report(key, work).generatedSourcesPaths' in text
    assert 'Elaboration.config' in text and 'Elaboration.top()' in text
    assert 'new demo.Core' in text
    assert 'spinaldb.Main' not in (tmp_path / 'rvw/build-db.sh').read_text()
    assert 'rvwcore.Database' in (tmp_path / 'rvw/build-db.sh').read_text()
    assert '${RVW_HOME}/RiscvSim/scripts' in (tmp_path / 'rvw.toml').read_text()
