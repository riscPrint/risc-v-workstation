"""CLI and MCP for the first SoC composition profile."""
import json
from rvw.soc.compose import compose


def register(sub):
    p = sub.add_parser('compose', help='generate an APB3 Spinal SoC from explicit project binders')
    p.add_argument('spec')
    p.add_argument('--out', required=True)
    p.add_argument('--elf')
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=run)


def run(args):
    try:
        result = compose(args.spec, args.out, args.elf)
        code = 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        result, code = dict(status='error', error=str(exc)), 2
    print(json.dumps(result))
    return code


def mcp_tools():
    from rvw.mcp.spec import ToolSpec, schema
    def execute(**args):
        return compose(**args)
    return [ToolSpec('soc_compose', 'Generate an APB3 RV32 Spinal top. Generation is not simulation evidence.',
                     schema({'source': {'type':'string'}, 'out': {'type':'string'}, 'elf': {'type':'string'}}, ['source','out']), execute)]
