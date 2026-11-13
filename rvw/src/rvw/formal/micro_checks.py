"""Project-instantiated microarchitecture rules with explicit interface contracts."""
NAMES = ('fifo_order', 'pipeline', 'mutex', 'arbiter', 'age_matrix', 'store_forward')


def render(kind, width, entries):
    if kind not in NAMES or not 1 <= width <= 64 or not 1 <= entries <= 64:
        raise ValueError('invalid microarchitecture template parameters')
    if kind == 'pipeline':
        from .simple_bus_checks import render as stream
        return stream('axis', width, entries).replace('module rvw_axis(', 'module rvw_pipeline(')
    if kind == 'fifo_order':
        ports=f'input push, pop, input [{width-1}:0] push_data, pop_data'
        body=f'''reg [{width-1}:0] data [0:{entries-1}];
integer head=0, tail=0, count=0;
always @(posedge clk) begin
 if(reset) begin head<=0; tail<=0; count<=0; end
 else begin
  assert(!pop || count>0);
  assert(!push || pop || count<{entries});
  if(pop && count>0) begin
   assert(pop_data == data[head]);
   head <= head=={entries-1} ? 0 : head+1;
  end
  if(push) begin data[tail]<=push_data; tail<=tail=={entries-1} ? 0 : tail+1; end
  case({{push,pop}}) 2'b10: count<=count+1; 2'b01: count<=count-1; endcase
 end
end'''
    elif kind in ('mutex', 'arbiter'):
        ports=f'input [{entries-1}:0] grants'
        body="always @(posedge clk) if(!reset) assert((grants & (grants-1'b1)) == 0);"
        if kind == 'arbiter':
            ports+=f', input enabled, input [{entries-1}:0] requests'
            body+=f'\nalways @(posedge clk) if(!reset) assert((grants & ~requests) == 0);\n'
            for i in range(entries):
                body+=f'''integer wait_{i}=0;
always @(posedge clk) begin
 if(reset || !enabled || !requests[{i}] || grants[{i}]) wait_{i}<=0;
 else begin assert(wait_{i}<BOUND); wait_{i}<=wait_{i}+1; end
end
'''
    elif kind == 'age_matrix':
        ports=f'input [{entries-1}:0] valid, input [{entries*entries-1}:0] older'
        lines=[]
        for i in range(entries):
            lines.append(f'if(valid[{i}]) assert(!older[{i*entries+i}]);')
            for j in range(i+1,entries):
                lines.append(f'if(valid[{i}] && valid[{j}]) assert(older[{i*entries+j}] != older[{j*entries+i}]);')
            for j in range(entries):
                for k in range(entries):
                    if len({i,j,k}) == 3:
                        lines.append(f'if(valid[{i}] && valid[{j}] && valid[{k}] && older[{i*entries+j}] && older[{j*entries+k}]) assert(older[{i*entries+k}]);')
        body='always @(posedge clk) if(!reset) begin\n'+'\n'.join(lines)+'\nend'
    else:
        ports=f'''input load_fire, forwarded, input [{entries-1}:0] valid, older, address_match, selected,
input [{width-1}:0] load_data, input [{entries*width-1}:0] store_data'''
        body=f'''wire [{entries-1}:0] eligible=valid & older & address_match;
reg [{entries-1}:0] expected;
integer i;
always @* begin
 expected=0;
 for(i=0;i<{entries};i=i+1) if(eligible[i]) expected=({entries}'d1 << i);
end
always @(posedge clk) if(!reset && load_fire) begin
 assert(forwarded == (eligible != 0));
 assert(selected == expected);
 for(integer j=0;j<{entries};j=j+1) if(expected[j]) assert(load_data == store_data[j*{width} +: {width}]);
end'''
    params='#(parameter integer BOUND=8)' if kind=='arbiter' else ''
    return f'module rvw_{kind}{params}(input clk, reset, '+ports+');\n'+body+'\nendmodule\n'

PORTS = {
    'allocation_pool': ('live','alloc0_valid','alloc1_valid','free0_valid','free1_valid','alloc0','alloc1','free0','free1'),
    'freelist_conservation': ('free_bits','live','alloc0_valid','alloc1_valid','free0_valid','free1_valid','alloc0','alloc1','free0','free1'),
    'rob': ('count','push','pop'),
    'credit': ('count','push','pop'),
    'freelist': ('free_bits','allocated'),
    'cam_match': ('active','require_match','match_bits'),
    'counter_bounds': ('active','value'),
    'fifo_order': ('push', 'pop', 'push_data', 'pop_data'),
    'pipeline': ('valid', 'ready', 'payload'),
    'mutex': ('grants',),
    'arbiter': ('grants', 'enabled', 'requests'),
    'age_matrix': ('valid', 'older'),
    'store_forward': ('load_fire', 'forwarded', 'valid', 'older', 'address_match', 'selected', 'load_data', 'store_data'),
}


def generate(spec, out):
    """Emit project-owned instance bindings; missing signals stay unsupported."""
    import json
    import re
    from pathlib import Path
    if spec.get('schema') != 'rvw.micro-checks/1':
        raise ValueError('expected rvw.micro-checks/1')
    path = re.compile(r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*')
    if not path.fullmatch(spec['top']):
        raise ValueError('invalid binding target')
    sources, binds, rows = [], [], []
    seen=set()
    for rule in spec['rules']:
        row=dict(id=rule['id'], kind=rule['kind'], status='unsupported')
        rows.append(row)
        try:
            name=rule['id']
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',name) or name in seen:
                raise ValueError('invalid or duplicate rule id')
            seen.add(name)
            kind=rule['kind']
            required={'clk','reset',*PORTS[kind]}
            if set(rule.get('ports',{})) != required:
                raise ValueError('bind exactly: '+', '.join(sorted(required)))
            if any(not isinstance(v,str) or not path.fullmatch(v) for v in rule['ports'].values()):
                raise ValueError('ports must name project RTL signals')
            from .invariants import render as render_any
            entries=rule.get('entries',4)
            source=render_any(kind,entries,rule.get('width',8))
            module='rvw_rule_'+name
            sources.append(source.replace('module rvw_'+kind,'module '+module,1))
            bound=rule.get('bound',8)
            if type(bound) is not int or not 1<=bound<=1024:
                raise ValueError('fairness bound must be in 1..1024')
            params=f' #(.BOUND({bound}))' if kind=='arbiter' else ''
            if kind in ('allocation_pool','freelist_conservation'):
                if kind=='allocation_pool' and 'usable' in rule:
                    raise ValueError('usable requires freelist_conservation')
                initial=rule.get('initial_live',0)
                usable=rule.get('usable',(1<<entries)-1)
                if any(type(v) is not int or not 0<=v<(1<<entries) for v in (initial,usable)) or initial & ~usable:
                    raise ValueError('initial_live and usable must fit entries, with initial_live a subset')
                params=f" #(.INITIAL_LIVE({entries}'d{initial})"
                if kind=='freelist_conservation':params+=f",.USABLE({entries}'d{usable})"
                params+=')'
                row['initial_live']=initial
                if kind=='freelist_conservation':row['usable']=usable
            binds.append('bind '+spec['top']+' '+module+params+' '+module+'_instance('+', '.join(
                '.'+k+'('+v+')' for k,v in sorted(rule['ports'].items()))+');')
            row.update(status='generated', ports=rule['ports'])
            if kind=='arbiter': row['bound']=bound
        except (ValueError, KeyError, TypeError) as exc:
            row['reason']=str(exc)
    out=Path(out)
    out.mkdir(parents=True,exist_ok=False)
    (out/'monitors.sv').write_text('\n'.join(sources))
    (out/'binds.sv').write_text('\n'.join(binds)+'\n')
    result=dict(schema='rvw.micro-generation/1',status='generated' if binds else 'no_checks',
                rules=rows,complete=bool(binds) and all(r['status']=='generated' for r in rows),
                limitations=['Project signal bindings are declared, not extracted or compiled.',
                             'No proof or simulator was run.'])
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
