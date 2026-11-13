import json
import shutil
import pytest
from rvw.formal.equiv_memory import aliases




@pytest.mark.fast
def test_memory_aliases_preserve_state_bits():
    module = {'cells':{'$mem$ram[0]':{'type':'$dff','connections':{'Q':[3,4]}}},
              'netnames':{'ram[0]':{'bits':[3,4],'hide_name':0,'attributes':{'init':'01'}}}}
    assert aliases(module) == 2
    assert 'ram[0]' not in module['netnames']
    assert any(row.get('attributes',{}).get('init')=='01' for row in module['netnames'].values())
    assert any(name.startswith('rvw_memory_state_') and row['bits']==[3,4]
               for name,row in module['netnames'].items())


@pytest.mark.slow
@pytest.mark.skipif(not all(shutil.which(x) for x in ('eqy','sby','yosys','yosys-abc')),reason='native formal tools')
@pytest.mark.parametrize('lag,broken',[(0,False),(1,False),(0,True)])
def test_ram_against_register_array(tmp_path,lag,broken):
    from rvw.cli import main
    gold=tmp_path/'gold.v'; gate=tmp_path/'gate.v'
    header='module top(input clk,reset,we,input [1:0] addr,input [3:0] data,output [3:0] q);\n'
    gold.write_text(header+'''reg [3:0] ram[0:3];
integer i;
always @(posedge clk) if(reset) begin for(i=0;i<4;i=i+1) ram[i]<=0; end
else if(we) ram[addr]<=data;
assign q=ram[addr]; endmodule
''')
    gate.write_text(header+'''reg [3:0] r0,r1,r2,r3;
always @(posedge clk) if(reset) begin r0<=0;r1<=0;r2<=0;r3<=0;end
else if(we) case(addr) 0:r0<=data;1:r1<=data;2:r2<=data;3:r3<=data;endcase
wire [3:0] value=addr==0?r0:addr==1?r1:addr==2?r2:r3;
'''+ ('reg [3:0] delayed; always @(posedge clk) delayed<=value; assign q=delayed;' if lag else 'assign q=value'+('^4\'d1' if broken else '')+';')+'endmodule')
    out=tmp_path/'proof'
    rc=main(['formal','equiv','--gold',str(gold),'--gate',str(gate),'--top','top',
             '--reset','reset','--memory-map','--unmatched-state','prove',
             '--latency',str(lag),'--timeout','40','--out',str(out)])
    result=json.loads((out/'result.json').read_text())
    assert result['status']==('not_equivalent' if broken else 'equivalent'), result
    assert rc==(1 if broken else 0)
