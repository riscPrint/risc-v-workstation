"""Literal single-control power switches and sampled settling contracts."""
import re

RTL=re.compile(r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*')


def parse(name,opts,domains):
    required={'-domain','-input_supply_port','-output_supply_port','-control_port','-on_state'}
    if set(opts)!=required or opts['-domain'] not in domains:
        raise ValueError('switch requires domain, input/output supply, control and on-state')
    pairs={}
    for key in ('-input_supply_port','-output_supply_port','-control_port'):
        values=opts[key].split()
        if len(values)!=2 or any(not RTL.fullmatch(v) for v in values):
            raise ValueError('switch ports require literal local name and net')
        pairs[key]=values
    on=opts['-on_state'].split()
    if len(on)!=3 or not RTL.fullmatch(on[0]) or on[1]!=pairs['-input_supply_port'][0] or on[2].lstrip('!')!=pairs['-control_port'][0] or on[2].count('!')>1:
        raise ValueError('only one control or its negation is supported')
    return dict(opts)


def generate(switches,bindings,top):
    if set(switches)!=set(bindings):
        raise ValueError('bind every power switch exactly')
    sources,binds=[],[]
    for name,strategy in switches.items():
        b=bindings[name]
        if set(b)!={'clk','reset','input_good','output_good','settle_cycles'}:
            raise ValueError('switch needs clock/reset, input/output availability and settle_cycles')
        bound=b['settle_cycles']
        if type(bound) is not int or not 1<=bound<=1024 or any(not isinstance(v,str) or not RTL.fullmatch(v) for k,v in b.items() if k!='settle_cycles'):
            raise ValueError('invalid power-switch bindings')
        module='rvw_upf_switch_'+name
        sources.append(f'''module {module}(input clk, reset, input_good, output_good, control);
wire desired=input_good && control;
reg previous=0, armed=0;
integer age=0;
always @(posedge clk) begin
 if(reset) begin age<=0; armed<=0; previous<=desired; end
 else begin
  armed<=1; previous<=desired;
  if(!armed || desired!=previous) begin
   age<=1;
   if({bound}==1) assert(output_good==desired);
  end else begin
   if(age<{bound}) age<=age+1;
   if(age>={bound-1}) assert(output_good==desired);
  end
 end
end
endmodule
''')
        ports={k:v for k,v in b.items() if k!='settle_cycles'}
        control=strategy['-control_port'].split()[1]
        ports['control']=('!' if strategy['-on_state'].split()[2].startswith('!') else '')+control
        binds.append('bind '+top+' '+module+' '+module+'_instance('+', '.join('.'+k+'('+v+')' for k,v in ports.items())+');')
    return sources,binds
