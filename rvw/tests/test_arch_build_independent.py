"""ELF builds need the cross compiler, not a timing simulator."""
import pytest
from rvw.arch import core

pytestmark=pytest.mark.fast


def test_build_does_not_resolve_gem5(tmp_path,monkeypatch):
    class Project:
        def get(self,section,key):return str(tmp_path)
    monkeypatch.setattr(core,'settings',lambda project:(Project(),None,dict(config='declared',isa='rv32im')))
    monkeypatch.setattr(core,'gem5_binary',lambda:pytest.fail('ELF build must not probe gem5'))
    monkeypatch.setattr(core,'executable',lambda value:value)
    monkeypatch.setattr(core,'tool_identity',lambda value:dict(path=value,version='test compiler'))
    def build(command,log):
        (tmp_path/'median.riscv').write_bytes(b'compiler output')
    monkeypatch.setattr(core,'invoke',build)
    result=core.build(bench='median')
    assert result['backend']=='riscv-gcc'
    assert result['benchmarks'][0]['sha256']
