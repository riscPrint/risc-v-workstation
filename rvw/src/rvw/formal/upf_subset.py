"""Literal sampled UPF safety subset. No Tcl interpreter is invoked."""
import hashlib
import json
import re
from pathlib import Path

IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
RTL = re.compile(r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*')


def parse(source):
    domains, strategies, retention, psts, switches = {}, {}, {}, {}, {}
    version = None
    source = source.replace('\\\n',' ')
    for number,line in enumerate(source.splitlines(),1):
        line=line.strip()
        if not line or line.startswith('#'): continue
        if any(c in line for c in '$[];"\\') or not re.fullmatch(r'(?:\s*(?:\{[^{}]*\}|[^{}\s]+))*\s*',line):
            raise ValueError(f'line {number}: only literal flat Tcl words are supported')
        words=[w[1:-1] if w.startswith('{') else w for w in re.findall(r'\{[^{}]*\}|[^{}\s]+',line)]
        if words == ['upf_version','2.1'] and version is None and not domains:
            version = '2.1'
            continue
        if version is None:
            raise ValueError('declare upf_version 2.1 first')
        if len(words)<2 or not IDENT.fullmatch(words[1]):
            raise ValueError(f'line {number}: declare a plain strategy/domain name')
        command,name,*args=words
        if len(args)%2 or len(set(args[::2])) != len(args[::2]):
            raise ValueError(f'line {number}: options require unique value pairs')
        opts=dict(zip(args[::2],args[1::2]))
        if command=='create_power_domain':
            if set(opts)!={'-elements'} or name in domains or not opts['-elements'].split():
                raise ValueError('power domains require unique names and literal elements')
            if any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_./]*|\.',p) for p in opts['-elements'].split()):
                raise ValueError('unsupported domain element pattern')
            domains[name]=dict(elements=opts['-elements'].split())
        elif command=='create_power_switch':
            from .upf_switches import parse as parse_switch
            if name in switches: raise ValueError('duplicate power switch')
            switches[name]=parse_switch(name,opts,domains)
        elif command=='create_pst':
            if set(opts)!={'-supplies'} or name in psts:
                raise ValueError('power-state table requires unique name and supplies')
            supplies=opts['-supplies'].split()
            if not supplies or len(supplies)!=len(set(supplies)) or any(not RTL.fullmatch(v) for v in supplies):
                raise ValueError('power-state supplies must be unique literal paths')
            psts[name]=dict(supplies=supplies,states={})
        elif command=='add_pst_state':
            if set(opts)!={'-pst','-state'} or opts['-pst'] not in psts:
                raise ValueError('power state requires a declared table and literal tuple')
            table=psts[opts['-pst']]
            values=opts['-state'].split()
            if name in table['states'] or len(values)!=len(table['supplies']) or any(not IDENT.fullmatch(v) for v in values):
                raise ValueError('power-state tuple must name one state per supply')
            table['states'][name]=values
        elif command=='set_retention':
            required={'-domain','-retention_power_net','-retention_ground_net','-save_signal','-restore_signal'}
            if set(opts)!=required or name in retention or opts['-domain'] not in domains:
                raise ValueError('retention requires unique strategy, domain, supplies and save/restore controls')
            for key in ('-retention_power_net','-retention_ground_net'):
                if not RTL.fullmatch(opts[key]): raise ValueError('retention supplies must be literal paths')
            for key in ('-save_signal','-restore_signal'):
                parts=opts[key].split()
                if len(parts)!=2 or not RTL.fullmatch(parts[0]) or parts[1] not in ('high','low'):
                    raise ValueError('sampled retention supports literal high/low controls only')
            retention[name]=opts
        elif command=='set_isolation':
            required={'-domain','-applies_to','-clamp_value','-isolation_signal','-isolation_sense'}
            if set(opts)!=required or name in strategies or opts['-domain'] not in domains:
                raise ValueError('isolation requires a known domain and explicit supported options')
            if opts['-applies_to']!='outputs' or opts['-clamp_value'] not in ('0','1') or opts['-isolation_sense'] not in ('high','low'):
                raise ValueError('only output isolation with binary clamp and high/low sense is supported')
            if not RTL.fullmatch(opts['-isolation_signal']):
                raise ValueError('isolation control must be a plain RTL path')
            if any(s['-domain']==opts['-domain'] for s in strategies.values()):
                raise ValueError('only one isolation strategy per domain is supported')
            strategies[name]=opts
        else:
            raise ValueError(f'unsupported UPF command {command}')
    if not domains:
        raise ValueError('declare at least one power domain')
    return dict(schema='rvw.upf-subset/1',upf_version=version,domains=domains,isolation=strategies,retention=retention,psts=psts,switches=switches)


def render(width, clamp, sense):
    active='isolate' if sense=='high' else '!isolate'
    return f'''module rvw_upf_isolation(input clk, reset, power_good, isolate, output_valid, consumer_use,
input [{width-1}:0] value);
wire isolated = {active};
reg previous_isolated=0, previous_power=1, armed=0;
always @(posedge clk) begin
 if(reset) begin armed<=0; previous_isolated<=isolated; previous_power<=power_good; end
 else begin
  if(isolated) assert(value == {width}'d{((1 << width)-1) if clamp else 0});
  if(!power_good) begin assert(isolated); assert(!output_valid); end
  if(consumer_use) assert(output_valid || isolated);
  if(armed && previous_power && !power_good) assert(previous_isolated);
  previous_isolated<=isolated; previous_power<=power_good; armed<=1;
 end
end
endmodule
'''


def generate(source, bindings, out):
    raw=Path(source).read_bytes()
    obj=parse(raw.decode())
    binding=json.loads(Path(bindings).read_text())
    if set(binding)-{'schema','top','event_model','domains','retention','psts','switches'} or binding['schema']!='rvw.upf-bindings/1' or binding['event_model']!='always_on_sampled':
        raise ValueError('require rvw.upf-bindings/1 and always_on_sampled event model')
    if not IDENT.fullmatch(binding['top']): raise ValueError('invalid bind top')
    if set(binding['domains'])!=set(obj['domains']): raise ValueError('bind every declared power domain')
    monitors,binds=[],[]
    for name,strategy in obj['isolation'].items():
        domain=strategy['-domain']; b=binding['domains'][domain]
        if set(b)!={'width','clk','reset','power_good','output_valid','consumer_use','value'}:
            raise ValueError('bind width, clock, reset, availability, consumer use and complete output value')
        width=b['width']
        if type(width) is not int or not 1<=width<=4096 or any(not isinstance(v,str) or not RTL.fullmatch(v) for k,v in b.items() if k!='width'):
            raise ValueError('invalid width or RTL signal path')
        module='rvw_upf_'+name
        monitors.append(render(width,int(strategy['-clamp_value']),strategy['-isolation_sense']).replace('module rvw_upf_isolation(', 'module '+module+'('))
        ports={k:v for k,v in b.items() if k!='width'}
        ports['isolate']=strategy['-isolation_signal']
        binds.append('bind '+binding['top']+' '+module+' '+module+'_instance('+', '.join('.'+k+'('+v+')' for k,v in ports.items())+');')
    rb=binding.get('retention',{})
    if set(rb)!=set(obj['retention']): raise ValueError('bind every retention strategy exactly')
    for name,strategy in obj['retention'].items():
        from .power_checks import render as power_render
        b=rb[name]
        if set(b)!={'width','clk','reset','power_good','functional_use','state'}:
            raise ValueError('retention requires width, sampling clock/reset, power, functional use and state')
        width=b['width']
        if type(width) is not int or not 1<=width<=64 or any(not isinstance(v,str) or not RTL.fullmatch(v) for k,v in b.items() if k!='width'):
            raise ValueError('invalid retention binding')
        module='rvw_upf_retention_'+name
        monitors.append(power_render('retention',width,1).replace('module rvw_retention(', 'module '+module+'('))
        ports={k:v for k,v in b.items() if k!='width'}
        for key,port in [('-save_signal','save'),('-restore_signal','restore')]:
            net,sense=strategy[key].split()
            ports[port]=net if sense=='high' else '~'+net
        binds.append('bind '+binding['top']+' '+module+' '+module+'_instance('+', '.join('.'+k+'('+v+')' for k,v in ports.items())+');')
    pb=binding.get('psts',{})
    if set(pb)!=set(obj['psts']): raise ValueError('bind every power-state table exactly')
    for name,table in obj['psts'].items():
        b=pb[name]
        if set(b)!={'clk','reset','supplies'} or set(b['supplies'])!=set(table['supplies']):
            raise ValueError('bind table clock/reset and every supply')
        if not table['states']: raise ValueError('power-state table has no legal states')
        ports={k:b[k] for k in ('clk','reset')}
        declarations=[];codes=[]
        for i,supply in enumerate(table['supplies']):
            mapping=b['supplies'][supply]
            if set(mapping)!={'signal','states'} or not mapping['states']:
                raise ValueError('supply requires signal and explicit state codes')
            values=list(mapping['states'].values())
            if any(type(v) is not int or not 0<=v<65536 for v in values) or len(set(values))!=len(values):
                raise ValueError('supply state codes must be unique unsigned 16-bit integers')
            width=max(1,max(values).bit_length())
            declarations.append(f'input [{width-1}:0] supply_{i}')
            ports[f'supply_{i}']=mapping['signal']
            codes.append((width,mapping['states']))
        if any(not isinstance(v,str) or not RTL.fullmatch(v) for v in ports.values()):
            raise ValueError('invalid table signal path')
        tuples=[]
        for values in table['states'].values():
            terms=[]
            for i,state in enumerate(values):
                width,mapping=codes[i]
                if state not in mapping: raise ValueError('missing supply state code '+state)
                terms.append(f"supply_{i} == {width}'d{mapping[state]}")
            tuples.append('('+' && '.join(terms)+')')
        module='rvw_upf_pst_'+name
        monitors.append('module '+module+'(input clk, reset, '+', '.join(declarations)+');\n'+
                        'always @(posedge clk) if(!reset) assert('+' || '.join(tuples)+');\nendmodule\n')
        binds.append('bind '+binding['top']+' '+module+' '+module+'_instance('+', '.join('.'+k+'('+v+')' for k,v in ports.items())+');')
    from .upf_switches import generate as generate_switches
    switch_sources,switch_binds=generate_switches(obj['switches'],binding.get('switches',{}),binding['top'])
    monitors.extend(switch_sources);binds.extend(switch_binds)
    report=dict(schema='rvw.upf-generation/1',status='generated' if binds else 'no_checks',
                source_sha256=hashlib.sha256(raw).hexdigest(),
                bindings_sha256=hashlib.sha256(Path(bindings).read_bytes()).hexdigest(),intent=obj,
                event_model='always_on_sampled',
                unmonitored_domains=sorted(set(obj['domains'])-{s['-domain'] for s in [*obj['isolation'].values(),*obj['retention'].values(),*obj['switches'].values()]}),
                limits=['Literal domains, isolation, retention, supply tables and single-control switches are supported.',
                        'Bindings declare observed outputs and supply availability; completeness is not established.',
                        'Retention supplies are named, not modeled; save/restore are sampled levels while power is on.',
                        'Supply tables check sampled declared state codes; no voltage or transition semantics are inferred.',
                        'Power-switch checking uses declared sampled settle bounds; no physical power behavior is inferred.',
                        'Clock gating import, edge controls and Tcl evaluation are unsupported.',
                        'No compilation, simulation, proof or physical power analysis was run.'])
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    (out/'monitors.sv').write_text('\n'.join(monitors)); (out/'binds.sv').write_text('\n'.join(binds)+'\n')
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def run(args):
    try:
        result=generate(args.source,args.bindings,args.out)
        print(json.dumps(result))
        return 0 if result['status']=='generated' else 3
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(f'UPF subset error: {exc}')
        return 2
