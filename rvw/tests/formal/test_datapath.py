import json
import shutil
from pathlib import Path
import pytest
from rvw.cli import main
from rvw.formal.bitc import translate

TOOLS = all(shutil.which(t) for t in ('yosys', 'cbmc'))

@pytest.mark.skipif(not TOOLS, reason='needs native Yosys and CBMC')
@pytest.mark.parametrize('width,mutant', [(8,False),(32,False),(64,False),(32,True)])
def test_symbolic_real_width(tmp_path, width, mutant):
    rtl, model = tmp_path/'dut.v', tmp_path/'ref.c'
    rtl.write_text(f'module dut(input [{width-1}:0] a,b, output [{width-1}:0] y); assign y=a {"^" if mutant else "+"} b; endmodule')
    model.write_text(f'uint64_t reference(uint64_t a,uint64_t b,uint64_t c,uint8_t rm,uint8_t *flags) {{return (a+b)&{(1<<width)-1}ULL;}}')
    out=tmp_path/'out'
    rc=main(['formal','datapath','--rtl',str(rtl),'--model',str(model),'--width',str(width),'--out',str(out)])
    result=json.loads((out/'result.json').read_text())
    assert result['status']==('counterexample' if mutant else 'proved'), result
    assert rc==(1 if mutant else 0)

@pytest.mark.skipif(not TOOLS, reason='needs native Yosys and CBMC')
@pytest.mark.parametrize('latency', [1,2])
def test_transaction_latency(tmp_path, latency):
    rtl, model=tmp_path/'dut.v',tmp_path/'ref.c'
    rtl.write_text('module dut(input clk,reset,start, input [7:0] a,b, output reg [7:0] y, output reg done); always @(posedge clk) begin if(reset) begin y<=0; done<=0; end else begin y<=a+b; done<=start; end end endmodule')
    model.write_text('uint64_t reference(uint64_t a,uint64_t b,uint64_t c,uint8_t rm,uint8_t *flags) {return (a+b)&255;}')
    out=tmp_path/'out'
    main(['formal','datapath','--rtl',str(rtl),'--model',str(model),'--width','8','--latency',str(latency),'--out',str(out)])
    result=json.loads((out/'result.json').read_text())
    assert result['status']==('proved' if latency==1 else 'counterexample'),result

@pytest.mark.skipif(not TOOLS, reason='needs native Yosys and CBMC')
def test_c_undefined_behavior_is_not_dut_counterexample(tmp_path):
    rtl,model=tmp_path/'dut.v',tmp_path/'ref.c'
    rtl.write_text('module dut(input [31:0] a,b,output [31:0] y); assign y=a/b; endmodule')
    model.write_text('uint64_t reference(uint64_t a,uint64_t b,uint64_t c,uint8_t rm,uint8_t *flags) {return a/b;}')
    out=tmp_path/'out'
    main(['formal','datapath','--rtl',str(rtl),'--model',str(model),'--width','32','--out',str(out),'--timeout','30'])
    result=json.loads((out/'result.json').read_text())
    assert result['status']=='inconclusive',result


def test_case_splitting_and_unknown_cells():
    from rvw.formal.datapath import case_expression
    assert '255' in case_expression('nan',32)
    assert case_expression('all',64)=='1'
    with pytest.raises(ValueError): case_expression('nan',8)
    mod={'ports':{'a':{'direction':'input','bits':[1]*32},'b':{'direction':'input','bits':[2]*32},'y':{'direction':'output','bits':[3]*32}},'cells':{'bad':{'type':'$assume','connections':{}}},'netnames':{}}
    with pytest.raises(ValueError,match='unsupported mapped cell'): translate({'modules':{'dut':mod}},32,0)

@pytest.mark.skipif(not shutil.which('clang'), reason='needs native clang')
def test_riscv_m_reference_corner_cases(tmp_path):
    import ctypes
    import subprocess
    root=Path(__file__).resolve().parents[3]/'SpinalChecks/c2rtl/models'
    source=tmp_path/'models.c'
    source.write_text('#include "riscv_m.h"\nuint64_t check(unsigned op,unsigned w,uint64_t a,uint64_t b) {return rvw_m(op,w,a,b);}')
    library=tmp_path/'models.dylib'
    subprocess.run(['clang','-shared','-fPIC','-I',str(root),str(source),'-o',str(library)],check=True)
    f=ctypes.CDLL(str(library)).check
    f.argtypes=[ctypes.c_uint,ctypes.c_uint,ctypes.c_uint64,ctypes.c_uint64];f.restype=ctypes.c_uint64
    for width in (32,64):
        mask=(1<<width)-1
        def signed(x): return x-(1<<width) if x>>(width-1) else x
        values=(0,1,2,mask,mask-1,1<<(width-1),(1<<(width-1))-1)
        for a in values:
            for b in values:
                sa,sb=signed(a),signed(b)
                q=(abs(sa)//abs(sb)) * (-1 if (sa<0) != (sb<0) else 1) if b else -1
                expected=[a*b,(sa*sb)>>width,(sa*b)>>width,(a*b)>>width,
                          q,a//b if b else mask,sa-q*sb if b else sa,a%b if b else a]
                for op,e in enumerate(expected): assert f(op,width,a,b)==e&mask
