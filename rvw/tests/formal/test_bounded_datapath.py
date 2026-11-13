import json
import shutil
import pytest
from rvw.cli import main
from rvw.formal.datapath_binding import bind

TOOLS = all(shutil.which(t) for t in ('yosys', 'cbmc'))


@pytest.mark.skipif(not TOOLS, reason='needs native Yosys and CBMC')
@pytest.mark.parametrize('operation,mutant,bound', [('mul', False, 10), ('div', False, 10), ('mul', True, 10), ('div', False, 1)])
def test_iterative_bound_and_binding(tmp_path, operation, mutant, bound):
    if operation == 'mul':
        initialize = 'x<=lhs; rem<=rhs; acc<=0;'
        step = "if(rem==0) begin valid<=1; busy<=0; result<=acc; end else begin if(rem[0]) acc<=acc+x; x<=x<<1; rem<=rem>>1; end"
        reference = '(a*b)&255'
    else:
        initialize = 'rem<=lhs&7; x<=(rhs&3)+1; acc<=0;'
        step = 'if(rem<x) begin valid<=1; busy<=0; result<=acc; end else begin rem<=rem-x; acc<=acc+1; end'
        reference = '(a&7)/((b&3)+1)'
    if mutant:
        step = step.replace('result<=acc', 'result<=acc^1')
    rtl = tmp_path/'unit.v'
    rtl.write_text('module UserUnit(input clock,rst,go,input [7:0] lhs,rhs,output reg valid,output reg [7:0] result); '
                   'reg busy; reg [7:0] x,rem,acc; always @(posedge clock) begin '
                   'if(rst) begin busy<=0;valid<=0;result<=0;x<=0;rem<=0;acc<=0;end '
                   'else if(go) begin busy<=1;valid<=0;'+initialize+'end '
                   'else if(busy) begin '+step+' end end endmodule')
    model = tmp_path/'ref.c'
    model.write_text('uint64_t reference(uint64_t a,uint64_t b,uint64_t c,uint8_t rm,uint8_t *flags) {return '+reference+';}')
    binding = tmp_path/'binding.json'
    binding.write_text(json.dumps({'top':'UserUnit','ports':{'clk':'clock','reset':'rst','start':'go','done':'valid','a':'lhs','b':'rhs','y':'result'}}))
    out = tmp_path/'out'
    main(['formal','datapath','--rtl',str(rtl),'--model',str(model),'--binding',str(binding),'--width','8','--max-latency',str(bound),'--out',str(out),'--timeout','90'])
    result = json.loads((out/'result.json').read_text())
    assert result['status'] == ('counterexample' if mutant or bound==1 else 'proved'), result
    assert result['max_latency'] == bound
    assert 'binding.json' in result['inputs']


def test_binding_cannot_hide_extra_ports_or_alias_ports():
    module = {'ports':{'left':{},'right':{},'unexpected':{}}}
    design = {'modules':{'Unit':module}}
    bound = bind(design, {'top':'Unit','ports':{'a':'left','b':'right'}})
    assert 'unexpected' in bound['modules']['dut']['ports']
    with pytest.raises(ValueError, match='distinct'):
        bind(design, {'top':'Unit','ports':{'a':'left','b':'left'}})
