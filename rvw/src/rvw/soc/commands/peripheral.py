import json
from pathlib import Path


def register(sub):
    p = sub.add_parser('peripheral', help='export a SpinalSoc peripheral register map and binder')
    p.add_argument('kind', choices=['clint','plic','gpio','timer','finisher','uart16550','uart16550-full','spi','i2c','watchdog','block'])
    p.add_argument('--name', required=True)
    p.add_argument('--base', required=True, type=lambda s:int(s,0))
    p.add_argument('--out', required=True)
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=run)


def run(args):
    try:
        result = peripheral(args.kind, args.name, args.base)
        with Path(args.out).open('x') as f:
            json.dump(result,f,indent=2)
        print(json.dumps(dict(status='generated', file=args.out)))
        return 0
    except (ValueError,OSError) as exc:
        print(json.dumps(dict(status='error',error=str(exc))))
        return 2


def mcp_tools():
    from rvw.mcp.spec import ToolSpec, schema
    return [ToolSpec('soc_peripheral', 'Get a bounded SpinalSoc register map and project binder.',
        schema({'kind':{'type':'string'}, 'name':{'type':'string'}, 'base':{'type':'integer'}}, ['kind','name','base']), peripheral, side_effects='read-only', native_tools=())]


def peripheral(kind, name, base):
    """Load the handler on first use."""
    from rvw.soc.peripherals import peripheral as implementation
    return implementation(kind, name, base)
