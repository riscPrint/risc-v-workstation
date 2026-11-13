import importlib.util,json
from pathlib import Path
import pytest
spec=importlib.util.spec_from_file_location('vectors',Path(__file__).resolve().parents[2]/'examples/vexiiriscv/rvw/fpu/datapath/spike_vectors.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
pytestmark=pytest.mark.fast

def test_spike_export_refuses_missing_operations(tmp_path):
    with pytest.raises(ValueError,match='each selected'):
        m.export(tmp_path,32,tmp_path/'vectors.txt')

def test_spike_export_preserves_result_bits_and_flags(tmp_path):
    names=['fadd.s','fmul.s','fdiv.s','fsqrt.s','fcvt.w.s','fcvt.s.w','fmadd.s','fsub.s','fcvt.wu.s','fcvt.s.wu']
    cases=[dict(name=name,width=32,xlen=32,rm=4,operands=[0x7f800001,0,1]) for name in names]
    expected=[dict(value=0xffffffff7fc00000,flags=16)]*len(cases)
    (tmp_path/'cases-plan.json').write_text(json.dumps(dict(cases=cases,expected=expected)))
    path=tmp_path/'vectors.txt'
    assert m.export(tmp_path,32,path)==10
    assert path.read_text().splitlines()[0]=='0 4 7f800001 0 1 7fc00000 10'
