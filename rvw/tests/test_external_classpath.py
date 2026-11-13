"""Cached external launcher rebuilds only when captured inputs change."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest

pytestmark = pytest.mark.fast
SCRIPT = Path(__file__).resolve().parents[2] / 'RiscvSim/scripts/classpath.py'
spec = importlib.util.spec_from_file_location('external_classpath', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_compile_reuse_and_invalidation(tmp_path, monkeypatch):
    here, core, repo = (tmp_path / p for p in ('adapter', 'core', 'tools'))
    for p in (here, core, repo): p.mkdir()
    (core / 'src').mkdir()
    source = core / 'src/Core.scala'
    source.write_text('first')
    jar = tmp_path / 'scala-library.jar'
    jar.write_bytes(b'jar')
    classes = tmp_path / 'classes'
    classes.mkdir()
    compiled = classes / 'Core.class'
    compiled.write_bytes(b'compiled')
    cp = str(classes) + ':' + str(jar)
    calls = []
    def run(cmd, **kw):
        calls.append(cmd)
        assert cmd[1] == 'sbt-project'
        return SimpleNamespace(stdout=iter([cp + '\n']), wait=lambda: 0)
    monkeypatch.setattr(module.subprocess, 'Popen', run)
    assert module.classpath(here, core, repo, 'sbt-project') == cp
    assert module.classpath(here, core, repo, 'sbt-project') == cp
    assert len(calls) == 1
    source.write_text('second')
    module.classpath(here, core, repo, 'sbt-project')
    assert len(calls) == 2
    compiled.write_bytes(b'changed externally')
    module.classpath(here, core, repo, 'sbt-project')
    assert len(calls) == 3
    monkeypatch.setenv('SBT_OPTS', '-different')
    module.classpath(here, core, repo, 'sbt-project')
    assert len(calls) == 4

    sdk = tmp_path / 'spinal'
    (sdk / 'core/src').mkdir(parents=True)
    spinal = sdk / 'core/src/Core.scala'
    spinal.write_text('first SDK')
    monkeypatch.setenv('RVW_SPINAL_SOURCE', str(sdk))
    module.classpath(here, core, repo, 'sbt-project')
    assert len(calls) == 5
    spinal.write_text('changed SDK')
    module.classpath(here, core, repo, 'sbt-project')
    assert len(calls) == 6
    axis = repo / 'scripts/sbt/SpinalAxis.scala'
    axis.parent.mkdir(parents=True)
    axis.write_text('changed axis')
    module.classpath(here, core, repo, 'sbt-project')
    assert len(calls) == 7


def test_compile_failure_never_reuses_stale_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(module.subprocess, 'Popen', lambda *a, **kw: SimpleNamespace(stdout=iter(['failed']), wait=lambda: 1))
    with pytest.raises(RuntimeError, match='compilation failed'):
        module.classpath(tmp_path, tmp_path, tmp_path, 'sbt-project')
    assert not (tmp_path / 'target/rvw-classpath.json').exists()
