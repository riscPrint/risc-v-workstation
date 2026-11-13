import json
import shutil
import pytest


@pytest.mark.slow
@pytest.mark.skipif(not all(shutil.which(t) for t in ('yosys','cbmc')),reason='native datapath tools')
@pytest.mark.parametrize('private',[False,True])
@pytest.mark.parametrize('reset_value',[0,255])
def test_async_reset_precedes_synchronous_capture(tmp_path,private,reset_value):
    from rvw.cli import main
    # The unreset q register must see the asynchronous reset value at the reset
    # edge. Treating both registers as ordinary synchronous registers is wrong.
    reset='b[0]' if private else 'reset'
    (tmp_path/'dut.v').write_text('module dut(input clk,reset,start,input [7:0] a,b,output reg done,output reg [7:0] y);reg [7:0] value;'
        f'always @(posedge clk or posedge {reset}) if({reset}) value<={reset_value};else value<=a;'
        'always @(posedge clk) begin if(reset)y<=value;done<=start;end endmodule')
    (tmp_path/'model.c').write_text('#include <stdint.h>\nuint64_t reference(uint64_t a,uint64_t b,uint64_t c,uint8_t rm,uint8_t *flags){*flags=0;return '+str(reset_value)+';}')
    out=tmp_path/'proof'
    rc=main(['formal','datapath','--rtl',str(tmp_path/'dut.v'),'--model',str(tmp_path/'model.c'),
             '--width','8','--latency','1','--timeout','30','--out',str(out)])
    report=json.loads((out/'result.json').read_text())
    assert report['status']==('inconclusive' if private else 'proved'),report
    if private:assert 'declared public' in report['reason']
    assert rc==(3 if private else 0)
