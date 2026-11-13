"""Conservative bit-level internal path checks on captured flattened RTL."""
import hashlib
import json
from pathlib import Path
import re
from collections import deque

from rvw.common.proc import run_group


def analyze(module, source, destination, *, max_nodes=200000):
    nets=module['netnames']
    if source not in nets or destination not in nets:
        raise ValueError('internal endpoint is absent from flattened RTL')
    origins=set(nets[source]['bits'])
    goals=set(nets[destination]['bits'])
    drivers={}
    unknown_directions=[]
    for name,cell in module['cells'].items():
        directions=cell.get('port_directions',{})
        if set(directions)!=set(cell['connections']):
            unknown_directions.append(name)
        inputs=[bit for port,bits in cell['connections'].items() if directions.get(port)=='input' for bit in bits if type(bit) is int]
        outputs=[bit for port,bits in cell['connections'].items() if directions.get(port)=='output' for bit in bits if type(bit) is int]
        # Unknown direction and black boxes cannot establish absence.
        opaque=not cell['type'].startswith('$') or set(directions)!=set(cell['connections'])
        for bit in outputs:
            drivers.setdefault(bit,[]).append((name,inputs,opaque))
    queue=deque(bit for bit in goals if type(bit) is int)
    parent={bit:None for bit in queue}
    incomplete=set(unknown_directions)
    found=None
    while queue:
        bit=queue.popleft()
        if bit in origins:
            found=bit
            break
        for cell,inputs,opaque in drivers.get(bit,[]):
            if opaque:
                incomplete.add(cell)
            for origin in inputs:
                if origin not in parent:
                    if len(parent)>=max_nodes:
                        incomplete.add('node limit')
                        continue
                    parent[origin]=(bit,cell)
                    queue.append(origin)
    path=[]
    while found is not None:
        step=parent[found]
        path.append(dict(bit=found,cell=step[1] if step else None))
        found=step[0] if step else None
    return dict(status='path_found' if path else 'incomplete' if incomplete else 'no_path',
                source=source,destination=destination,witness=path,opaque=sorted(incomplete),
                visited_bits=len(parent),scope='conservative directed RTL dependency graph; no value-transfer or design-acceptance verdict')


def check(files,top,source,destination,out,timeout=60,max_nodes=200000):
    identifier=r'[A-Za-z_][A-Za-z0-9_$]*'
    if not re.fullmatch(identifier,top):
        raise ValueError('top must be a plain identifier')
    for endpoint in (source,destination):
        if not re.fullmatch(identifier+r'(?:\.'+identifier+')*',endpoint):
            raise ValueError('endpoints must be plain dot-separated RTL names')
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    reads=[];hashes={}
    for i,path in enumerate(files):
        raw=Path(path).read_bytes()
        if re.search(rb'(?m)^\s*`include\b',raw):
            raise ValueError('use self-contained RTL; includes are not captured')
        target=out/f'input_{i}.sv';target.write_bytes(raw)
        reads.append(f'read_verilog -formal -sv {target.name}')
        hashes[str(path)]=hashlib.sha256(raw).hexdigest()
    if not reads:
        raise ValueError('declare RTL files')
    commands=reads+[f'hierarchy -check -top {top}','proc','flatten','memory_map','write_json flattened.json']
    (out/'flatten.ys').write_text('\n'.join(commands)+'\n')
    with (out/'flatten.log').open('w') as log:
        result=run_group(['yosys','-Q','-T','-s','flatten.ys'],cwd=out,stdout=log,stderr=log,timeout=timeout)
    if result.returncode or result.timed_out:
        raise ValueError('native flattening failed; see flatten.log')
    data=json.loads((out/'flattened.json').read_text())
    result=analyze(data['modules'][top],source,destination,max_nodes=max_nodes)
    result.update(schema='rvw.internal-path/1',source_sha256=hashes,
                  flattened_sha256=hashlib.sha256((out/'flattened.json').read_bytes()).hexdigest())
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main(args):
    import math
    try:
        if not math.isfinite(args.timeout) or not 0<args.timeout<120 or args.max_nodes<1:
            raise ValueError('timeout must be positive and under 120 seconds; max-nodes must be positive')
        result=check(args.verilog,args.top,args.source,args.destination,args.out,args.timeout,args.max_nodes)
        print(json.dumps(result) if args.json else result['status'])
        return 0 if result['status']=='no_path' else 1 if result['status']=='path_found' else 3
    except (ValueError,OSError,KeyError) as exc:
        print(json.dumps(dict(status='error',error=str(exc))))
        return 2


def register(sub):
    parser=sub.add_parser('internal-path',help='check conservative internal RTL dependencies without cutting drivers')
    parser.add_argument('source')
    parser.add_argument('destination')
    parser.add_argument('--verilog',nargs='+',required=True)
    parser.add_argument('--top',required=True)
    parser.add_argument('--out',required=True)
    parser.add_argument('--timeout',type=float,default=60)
    parser.add_argument('--max-nodes',type=int,default=200000)
    parser.add_argument('--json',action='store_true')
    parser.set_defaults(func=main)


def mcp_tools():
    import sys
    from rvw.mcp.spec import ToolSpec,ToolError
    def execute(job,**args):
        source,destination=args.pop('source'),args.pop('destination')
        argv=[sys.executable,'-m','rvw','formal','internal-path',source,destination]
        for key,value in args.items():
            argv += ['--'+key.replace('_','-')]
            argv += value if isinstance(value,list) else [str(value)]
        code=job.run(argv)
        path=Path(args['out'])/'result.json'
        if code not in (0,1,3) or not path.is_file():
            raise ToolError('internal path check failed',{'exit_code':code})
        result=json.loads(path.read_text())
        if {'no_path':0,'path_found':1,'incomplete':3}.get(result.get('status'))!=code:
            raise ToolError('internal path exit and result disagree')
        return result
    properties={key:{'type':'string'} for key in ('source','destination','top','out')}
    properties.update(verilog={'type':'array','items':{'type':'string'}},timeout={'type':'number'},max_nodes={'type':'integer'})
    return [ToolSpec('formal_internal_path','Check conservative internal RTL paths. No Boolean influence or design acceptance verdict.',
                     {'type':'object','properties':properties,'required':['source','destination','top','out','verilog'],'additionalProperties':False},execute,long=True, side_effects='long-running; writes generated artifacts and reports to out; launches selected native tools', native_tools=('Yosys',))]
