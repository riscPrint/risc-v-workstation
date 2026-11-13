import importlib.util
from pathlib import Path
import pytest


ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('mul_smoke',ROOT/'examples/vexriscv/formal/mul-smoke.py')
example=importlib.util.module_from_spec(spec);spec.loader.exec_module(example)


def module():
    a=list(range(2,35));b=list(range(35,68));y=list(range(68,134))
    return {'netnames':{'memory_MUL_OPA':{'bits':a},'memory_MUL_OPB':{'bits':b},'_zz_memory_MUL_1':{'bits':y}},
            'cells':{'real_mul':{'type':'$mul','connections':{'A':a+[a[-1]]*33,'B':b+[b[-1]]*33,'Y':y},
                                 'parameters':{'A_SIGNED':'1','B_SIGNED':'1'}}}}


@pytest.mark.fast
def test_extract_preserves_cell_and_extension():
    source=module();sub,name,cell,product=example.extract(source)
    assert name=='real_mul'
    assert sub['cells'][name]==source['cells'][name]
    assert sub['ports']['a33']['bits']==source['netnames']['memory_MUL_OPA']['bits']
    assert len(sub['ports']['a33']['bits'])==33 and len(product)==66
    sub['cells'][name]['parameters']['A_SIGNED']='0'
    assert source['cells'][name]['parameters']['A_SIGNED']=='1'


@pytest.mark.fast
def test_unexpected_operand_wiring_is_refused():
    source=module();source['cells']['real_mul']['connections']['A'][-1]=9999
    with pytest.raises(ValueError,match='unexpected product interface'):
        example.extract(source)


@pytest.mark.slow
@pytest.mark.skipif(__import__('shutil').which('yosys') is None or __import__('shutil').which('cbmc') is None,reason='native datapath tools')
def test_hierarchical_datapath_ignores_scope_metadata(tmp_path):
    import json
    from rvw.cli import main
    (tmp_path/'dut.v').write_text('module adder(input [7:0] a,b,output [7:0] y);assign y=a+b;endmodule\nmodule dut(input [7:0] a,b,output [7:0] y);adder cell0(a,b,y);endmodule')
    (tmp_path/'model.c').write_text('#include <stdint.h>\nuint64_t reference(uint64_t a,uint64_t b,uint64_t c,uint8_t rm,uint8_t *flags){*flags=0;return (a+b)&255;}')
    assert main(['formal','datapath','--rtl',str(tmp_path/'dut.v'),'--model',str(tmp_path/'model.c'),
                 '--width','8','--timeout','30','--out',str(tmp_path/'proof')])==0
    result=json.loads((tmp_path/'proof/result.json').read_text())
    assert result['status']=='proved'
