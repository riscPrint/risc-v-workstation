import json
import pytest
from test_init_native_bindings import core
from rvw.init.soc_scaffold import wrapper
from rvw.soc.scaffold import new
pytestmark=pytest.mark.fast


def test_wrapper_buffers_accepted_transaction():
    text=wrapper(core())
    assert 'extends Component with SimpleCoreWrapper' in text
    assert 'pending && io.bus.ready' in text
    assert 'drive("ready", (!pending).asBits)' in text
    assert 'drive("rsp", (pending && io.bus.ready && !write).asBits)' in text


def test_soc_new_uses_project_adapter(tmp_path, monkeypatch):
    (tmp_path/'rvw').mkdir()
    (tmp_path/'rvw/build.sbt').write_text('ProjectRef(coreSource, "core")')
    (tmp_path/'rvw/core-map.json').write_text(json.dumps(core()))
    (tmp_path/'rvw.toml').write_text('[project]\nschema="rvw.project/1"\nroot="."\n[core]\nname="testcore"\n')
    monkeypatch.chdir(tmp_path)
    result=new('board',tmp_path/'soc')
    assert result['core']=='mapped_wrapper'
    spec=json.loads((tmp_path/'soc/compose.json').read_text())
    assert spec['core']['bus']=='simple'
    assert 'Class.forName("Example")' in (tmp_path/'soc/src/main/scala/ProjectCore.scala').read_text()
