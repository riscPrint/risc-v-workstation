"""Read project check requirements without changing project files."""
import json
import tempfile
import re
from pathlib import Path
from rvw.common.project import load_project


def plan(project, manifest=None, inventory=None):
    from rvw.formal.micro_checks import PORTS
    from rvw.formal.ooo_checks import PORTS as OOO_PORTS
    loaded=load_project(project)
    if loaded is None:
        raise ValueError('select a project with rvw.toml')
    root=loaded.path.parent
    source=Path(manifest) if manifest else root/'checks.generate.json'
    spec=json.loads(source.read_text()) if source.exists() else {}
    if not isinstance(spec,dict):
        raise ValueError('expected rvw.check-generation/1 object')
    if spec and spec.get('schema') != 'rvw.check-generation/1':
        raise ValueError('expected rvw.check-generation/1')
    generated = {}
    if source.exists():
        from rvw.checks.generate import generate
        with tempfile.TemporaryDirectory(prefix='rvw-check-plan-') as directory:
            report=generate(loaded.path,Path(directory)/'generated',source)
            generated={r['kind']:r for r in report['checks']}
    rows=[]
    requirements={
        'streams': 'Stream/Flow types and inventory in a design database; reviewed cancellation contracts',
        'buses': 'AXI4/Lite, TileLink, APB, AHB or Stream bus types in a design database; clock/reset and issuing limits',
        'csrs': 'CSR access policy, accepted access events and observed state/read signals',
        'power': 'UPF intent and explicit isolation, retention, power and clock signal bindings',
        'cdc': 'Clock/reset domains and explicit crossing signal bindings'}
    for kind,need in requirements.items():
        rows.append(dict(kind=kind,needs=need,declared=kind in spec,
                         binding=spec.get(kind),status=generated.get(kind,{}).get('status','unbound'),
                         instances=generated.get(kind,{}).get('instances',[]),
                         reason=generated.get(kind,{}).get('reason') if kind in spec else 'no project data supplied'))
    declared=[]
    queue=spec.get('queues')
    if isinstance(queue,str):
        data=json.loads((source.parent/queue).read_text())
        if data.get('schema') != 'rvw.micro-checks/1':
            raise ValueError('expected rvw.micro-checks/1')
        declared=data.get('rules',[])
    from rvw.formal.invariants import NAMES
    from rvw.formal.micro_checks import PORTS
    instances={r['id']:r for r in generated.get('queues',{}).get('instances',[])}
    for kind in dict.fromkeys(NAMES):
        ports=PORTS.get(kind)
        if ports is None:
            from rvw.formal.invariants import render
            try:
                header=render(kind,4,8).split(');',1)[0]
                ports=[]
                for group in re.split(r'\binput\s+',header)[1:]:
                    group=re.sub(r'\[[^]]*\]','',group)
                    for item in group.split(','):
                        name=item.strip().rstrip(')').strip()
                        if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',name):
                            ports.append(name)
            except ValueError:
                ports=[]

        matches=[r for r in declared if r.get('kind')==kind]
        required={'clk','reset',*ports}
        bindings=[dict(id=r['id'],signals=r.get('ports',{}),
                       missing=sorted(required-set(r.get('ports',{}))),
                       status=instances.get(r['id'],{}).get('status','unbound'),
                       reason=instances.get(r['id'],{}).get('reason')) for r in matches]
        from rvw.checks.declarations import template
        rows.append(dict(kind=kind,needs=sorted(required),declaration=template(kind),
                         declaration_file='rvw/templates/checks.micro.json' if kind in PORTS or kind in OOO_PORTS else None,declared=bool(matches),
                         bindings=bindings,status='generated' if any(b['status']=='generated' for b in bindings) else 'unbound',
                         reason=None if matches else 'no project signal binding supplied'))
    if inventory is not None:
        file=Path(inventory)
        if not file.is_absolute():
            file=root/file
        report=json.loads(file.read_text())
        if report.get('schema') != 'rvw.checks/1':
            raise ValueError('expected rvw.checks/1 inventory')
        by_kind={r['kind']:r for r in rows}
        for check in report['checks']:
            row=by_kind.get(check['kind'])
            if row is None:
                row=dict(kind=check['kind'],needs='Elaborated type or explicit Scala rule binding; see signal roles',
                         declared=True,status='unbound')
                rows.append(row)
                by_kind[check['kind']]=row
            row.setdefault('declaration', 'Call spinalchecks.DeclaredChecks.rule with this kind, a name, a meaning, an activation trigger and a failing condition in the sampling clock domain.')
            row.setdefault('native_bindings',[]).append(dict(id=check['id'],status=check['status'],
                signals=check.get('signals',{}),trigger_signal=check.get('trigger_signal')))
            row['native_inserted']=sum(c['status']=='inserted' for c in row['native_bindings'])
    return dict(schema='rvw.check-plan/1' ,project=str(loaded.path),checks=rows,
                limitations=['Declared bindings are not compiled or verified.',
                             'Generated means checker sources with declared bindings, not compiled RTL or passing evidence.',
                             'Custom Scala DeclaredChecks require their elaborated inventory and are outside this generator catalogue.'])


def run(args):
    try:
        print(json.dumps(plan(getattr(args,'project',None),args.manifest,getattr(args,'inventory',None)),indent=2))
        return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps(dict(status='error',error=str(exc))))
        return 2


def register(sub):
    p=sub.add_parser('plan',help='list check kinds, required inputs and declared project bindings')
    p.add_argument('--manifest')
    p.add_argument('--inventory',help='optional elaborated checks inventory, relative to the project')
    p.add_argument('--json',action='store_true')
    p.set_defaults(func=run)


def invoke(**args):
    return plan(args.get('project'),args.get('manifest'),args.get('inventory'))


def mcp_tools():
    from rvw.mcp.spec import ToolSpec,schema
    return [ToolSpec('checks_plan','List check kinds, binding requirements and project declarations.',
        schema({k:{'type':'string'} for k in ('project','manifest','inventory')},['project']),
        invoke,side_effects='read-only',native_tools=())]
