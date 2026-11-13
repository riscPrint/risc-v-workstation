import json
from pathlib import Path
import pytest
from rvw.sim.native_profiles import Profile,sha


def fixture(tmp_path):
    rtl=tmp_path/'top.v';rtl.write_text('module Top;endmodule')
    cc=tmp_path/'compiler';cc.write_bytes(b'compiler')
    verilator=tmp_path/'verilator';verilator.write_bytes(b'verilator')
    elf=tmp_path/'training.elf';elf.write_bytes(b'ELF fixture bytes')
    return rtl,cc,verilator,elf


def test_profile_capture_and_stale_input_rejection(tmp_path,monkeypatch):
    for name in ('CXX','CC','CFLAGS','CXXFLAGS','CPPFLAGS','LDFLAGS','MAKEFLAGS','MFLAGS','GNUMAKEFLAGS'):
        monkeypatch.delenv(name,raising=False)
    rtl,cc,verilator,elf=fixture(tmp_path)
    generate=tmp_path/'generate.json';generate.write_text(json.dumps(dict(schema='rvw.native-build-profile/1',compiler_pgo='generate',training_elf=elf.name)))
    out=tmp_path/'gen';out.mkdir()
    trained=Profile(generate,[rtl],str(cc),str(verilator),out)
    binding=trained.record['binding']
    assert binding['training_elf_sha256']==sha(elf)
    assert Path(binding['training_elf']).read_bytes()==elf.read_bytes()
    data=tmp_path/'data.profdata';data.write_bytes(b'profile bytes')
    manifest=tmp_path/'reuse.json'
    manifest.write_text(json.dumps(dict(binding,schema='rvw.compiler-pgo/1',profile=data.name,profile_sha256=sha(data))))
    use=tmp_path/'use.json';use.write_text(json.dumps(dict(schema='rvw.native-build-profile/1',compiler_pgo='use',reuse_manifest=manifest.name)))
    reused_out=tmp_path/'use';reused_out.mkdir()
    reused=Profile(use,[rtl],str(cc),str(verilator),reused_out)
    assert any(flag.startswith('-fprofile-instr-use=') for flag in reused.cpp)
    data.write_bytes(b'changed profile')
    invalid=tmp_path/'invalid';invalid.mkdir()
    with pytest.raises(ValueError,match='digest differs'):Profile(use,[rtl],str(cc),str(verilator),invalid)
    rtl.write_text('module Changed;endmodule')
    invalid_rtl=tmp_path/'changed';invalid_rtl.mkdir()
    with pytest.raises(ValueError,match='stale compiler profile'):Profile(use,[rtl],str(cc),str(verilator),invalid_rtl)


def test_inherited_flags_and_outdated_native_profile_fail_closed(tmp_path,monkeypatch):
    rtl,cc,verilator,elf=fixture(tmp_path)
    config=tmp_path/'profile.json';config.write_text('{"schema":"rvw.native-build-profile/1"}')
    monkeypatch.setenv('CXXFLAGS','-DUNRECORDED')
    out=tmp_path/'out';out.mkdir()
    with pytest.raises(ValueError,match='inherited'):Profile(config,[rtl],str(cc),str(verilator),out)
    import types
    from rvw.sim import native_models
    monkeypatch.setattr(native_models,'run_group',lambda *a,**k:types.SimpleNamespace(
        stdout='PROFOUTOFDATE',stderr='',returncode=0,timed_out=False))
    with pytest.raises(ValueError,match='native build failed'):native_models.step(['unused'],tmp_path)
