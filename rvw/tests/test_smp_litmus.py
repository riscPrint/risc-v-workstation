import hashlib
import importlib.util
from pathlib import Path
import pytest

pytestmark=pytest.mark.fast
path=Path(__file__).resolve().parents[2]/'examples/smp/rvw/litmus_programs.py'
spec=importlib.util.spec_from_file_location('smp_litmus',path)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture(tmp_path,monkeypatch,instruction='sw x5,0(x6)',columns='P0 | P1 ;'):
    text=f'''RISCV example
{{0:x5=1; 0:x6=x; 1:x6=y;}}
{columns}
 {instruction} | lw x5,0(x6) ;
exists
(1:x5=0)
'''
    p=tmp_path/'test.litmus';p.write_text(text)
    monkeypatch.setattr(module,'PINS',dict(cases={'test':hashlib.sha256(p.read_bytes()).hexdigest()}))
    return p


def test_parse_binds_harts_addresses_and_projection(tmp_path,monkeypatch):
    p=fixture(tmp_path,monkeypatch)
    regs,body,projection,digest=module.parse(p)
    assert regs==[{5:1,6:0x81000000},{6:0x81000040}]
    assert body==[['sw x5,0(x6)'],['lw x5,0(x6)']]
    assert projection==['1:x5']
    p.write_text(p.read_text()+'\n')
    with pytest.raises(ValueError,match='pinned litmus bytes'):
        module.parse(p)


@pytest.mark.parametrize('instruction',['lr.d x5,(x6)','sw x31,0(x6)','j somewhere'])
def test_unsupported_litmus_refuses_to_build(tmp_path,monkeypatch,instruction):
    p=fixture(tmp_path,monkeypatch,instruction)
    with pytest.raises(ValueError,match='unsupported litmus instruction'):
        module.build(p,tmp_path/'out')
    assert not (tmp_path/'out').exists()
