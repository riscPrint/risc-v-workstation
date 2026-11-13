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


def test_declared_native_inputs_bind_runtime_and_selected_sources(tmp_path):
    from rvw.uvm.native_inputs import capture
    repo,src,build,data=fixture(tmp_path)
    lib=tmp_path/'shim.so';lib.write_bytes(b'abi6')
    cpp=repo/'bridge.cpp';cpp.write_text('bridge')
    data['manifest']['sources'].append(str(cpp))
    data['manifest']['build_args']=['-CFLAGS','-I/project/headers']
    data['input_sha256'][str(cpp)]=sha(cpp)
    data['native_dependency_sha256']=capture([lib])
    (build/'build.json').write_text(json.dumps(data))
    first,_=identity(build,repo,repo,[1])
    config=tmp_path/'native.toml';configure(build,repo,config)
    assert str(lib) in config.read_text()
    lib.write_bytes(b'changed')
    with pytest.raises(ValueError,match='native dependency changed'):
        identity(build,repo,repo,[1])
    data['native_dependency_sha256']=capture([lib])
    (build/'build.json').write_text(json.dumps(data))
    assert identity(build,repo,repo,[1])[0]!=first


def test_external_source_requires_explicit_native_binding(tmp_path):
    from rvw.uvm.native_inputs import capture
    repo,src,build,data=fixture(tmp_path)
    external=tmp_path/'generated.sv';external.write_text('module generated; endmodule')
    data['input_sha256'][str(external)]=sha(external)
    (build/'build.json').write_text(json.dumps(data))
    with pytest.raises(ValueError,match='declared native dependency'):
        identity(build,repo,repo,[1])
    data['native_dependency_sha256']=capture([external])
    (build/'build.json').write_text(json.dumps(data))
    identity(build,repo,repo,[1])


def test_changed_native_dependency_cannot_launch_or_create_run(tmp_path):
    from rvw.uvm.native_inputs import capture
    from rvw.uvm.flow import run
    repo,src,build,data=fixture(tmp_path)
    library=tmp_path/'shim.so';library.write_bytes(b'original')
    data['native_dependency_sha256']=capture([library])
    (build/'build.json').write_text(json.dumps(data))
    library.write_bytes(b'changed')
    out=tmp_path/'run'
    with pytest.raises(ValueError,match='native dependency changed'):
        run(build,out,test='smoke')
    assert not out.exists()


def test_gate_runtime_bundle_omits_compiler_intermediates(tmp_path):
    from rvw.regress.config import load_config
    repo,src,build,data=fixture(tmp_path)
    (build/'obj/large-generated.cpp').write_text('compiler intermediate')
    (build/'library').mkdir();(build/'library/LICENSE.txt').write_text('license')
    config=tmp_path/'core.toml';configure(build,repo,config)
    runtime=tmp_path/'core.toml.runtime'
    assert (runtime/'build.json').read_bytes()==(build/'build.json').read_bytes()
    assert (runtime/'obj/simulation').read_bytes()==(build/'obj/simulation').read_bytes()
    assert (runtime/'library/LICENSE.txt').read_text()=='license'
    assert not (runtime/'obj/large-generated.cpp').exists()
    loaded=load_config(str(config))
    assert str(runtime) in loaded.adapter and str(build) not in loaded.adapter
    assert build/'obj/simulation' in loaded.cache_paths
