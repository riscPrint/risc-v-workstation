import json
import shutil
import pytest
from rvw.sec.latency import run
pytestmark=pytest.mark.slow


@pytest.mark.parametrize('leak',[True,False])
def test_unit_latency(tmp_path,leak):
    if not all(shutil.which(t) for t in ('yosys','verilator')): pytest.skip('native tools required')
    (tmp_path/'unit.sv').write_text('''module unit(input clk,reset,start,operand,output reg done);
reg [3:0] count;reg active;
always @(posedge clk) begin
 if(reset) begin done<=0;count<=0;active<=0;end
 else begin
 done<=0;
 if(start) begin active<=1;count<=0;end
 else if(active) begin
 if(count==LIMIT) begin done<=1;active<=0;end else count<=count+1;
 end
 end
end
endmodule
'''.replace('LIMIT','(operand ? 2 : 1)' if leak else '1'))
    p=dict(rtl='unit.sv',top='unit',clock='clk',reset='reset',start='start',done='done',operands=['operand'],
           pairs=[dict(operation='declared crypto op',a={'operand':0},b={'operand':1})],max_cycles=8)
    (tmp_path/'plan.json').write_text(json.dumps(p))
    result=run(tmp_path/'plan.json',tmp_path/'out')
    assert result['status']==('violation' if leak else 'no_leak_observed'),result
