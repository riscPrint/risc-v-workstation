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
    entry = (tmp_path / 'rvw/src/main/scala/rvwcore/Elaboration.scala').read_text()
    # The adapter can be rewritten while mapping signals without losing the database entry.
    assert 'new demo.Core' in entry and 'object Database' in entry and 'object Database' not in text
    assert 'spinaldb.Main' not in (tmp_path / 'rvw/build-db.sh').read_text()
    assert 'rvwcore.Database' in (tmp_path / 'rvw/build-db.sh').read_text()
    assert '${RVW_HOME}/RiscvSim/scripts' in (tmp_path / 'rvw.toml').read_text()


def test_debug_config_and_build_output_ignores(tmp_path, monkeypatch):
    import tomllib
    monkeypatch.setenv("RVW_HOME", str(tmp_path))
    (tmp_path / 'build.sbt').write_text('val spinalVersion = "1.15.0"\nlazy val cpu = project\n')
    result = scaffold(tmp_path, isa='rv32i', sbt_project='cpu', name='demo')
    project = tomllib.loads((tmp_path / 'rvw.toml').read_text())
    debug = tomllib.loads((tmp_path / project['debug']['config']).read_text())
    assert debug['core'] == {'name': 'demo', 'source_env': 'RVW_CORE_SOURCE', 'period': 10}
    assert '/target/' in (tmp_path / '.gitignore').read_text()
    other = tmp_path / 'other'
    other.mkdir()
    (other / 'build.sbt').write_text('val spinalVersion = "1.15.0"\nlazy val cpu = project\n')
    (other / '.gitignore').write_text('*.log\n')
    result = scaffold(other, isa='rv32i', sbt_project='cpu', name='demo')
    assert (other / '.gitignore').read_text() == '*.log\n'
    assert any('/target/' in step for step in result['next'])
