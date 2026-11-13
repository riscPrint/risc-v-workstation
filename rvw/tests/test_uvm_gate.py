"""C4 UVM bindings reject changed inputs and failed native matrices."""
import json
from pathlib import Path
import pytest
from rvw.sim.uvm import sha
from rvw.uvm.gate import identity,configure,adapter_main

pytestmark=pytest.mark.fast

def fixture(tmp_path):
    repo=tmp_path/'repo';repo.mkdir()
    src=repo/'top.sv';src.write_text('module top; endmodule\n')
    build=tmp_path/'build';(build/'obj').mkdir(parents=True)
    (build/'obj/simulation').write_text('binary')
    data=dict(status='pass',manifest=dict(name='bench',sources=[str(src)],tests=['smoke'],build_args=[]),
        input_sha256={str(src):sha(src)},binary_sha256=sha(build/'obj/simulation'),uvm_commit='pin',uvm_archive_sha256='archive')
    (build/'build.json').write_text(json.dumps(data))
    return repo,src,build,data


def test_source_binary_and_seed_binding(tmp_path):
    repo,src,build,data=fixture(tmp_path)
    digest,_=identity(build,repo,repo,[1,3])
    assert identity(build,repo,repo,[1])[0]!=digest
    selected=tmp_path/'selected';selected.mkdir();(selected/'top.sv').write_text('different')
    with pytest.raises(ValueError,match='selected source'): identity(build,repo,selected,[1,3])
    (build/'obj/simulation').write_text('changed')
    with pytest.raises(ValueError,match='binary changed'): identity(build,repo,repo,[1,3])


def test_config_loads_and_captures_dependencies(tmp_path):
    from rvw.regress.config import load_config
    repo,src,build,data=fixture(tmp_path)
    out=tmp_path/'core.toml';configure(build,repo,out)
    config=load_config(str(out))
    assert config.identity_capture and config.input_complete
    assert src in config.cache_paths and build/'obj/simulation' in config.cache_paths
    assert config.suites['uvm'].kind=='build'
    with pytest.raises(FileExistsError): configure(build,repo,out)
    data['manifest']['build_args']=['-LDFLAGS','-lcustom']
    (build/'build.json').write_text(json.dumps(data))
    with pytest.raises(ValueError,match='pure SV'): identity(build,repo,repo,[1])


def test_failed_or_empty_matrix_is_not_success(tmp_path,monkeypatch):
    repo,src,build,data=fixture(tmp_path)
    monkeypatch.setenv('RVW_CAPTURE_SOURCE','{}');monkeypatch.setenv('RVW_UVM_SOURCE',str(repo))
    monkeypatch.setattr('rvw.uvm.gate.flow.regress',lambda *a,**kw: {'tests':[{'status':'fail'}]})
    assert adapter_main([str(build),str(repo),'[1]','build'])==2
    monkeypatch.setattr('rvw.uvm.gate.flow.regress',lambda *a,**kw: {'tests':[]})
    assert adapter_main([str(build),str(repo),'[1]','build'])==2
