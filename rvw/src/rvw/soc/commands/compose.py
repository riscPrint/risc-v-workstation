"""CLI and MCP for the first SoC composition profile."""
import json


def register(sub):
    p = sub.add_parser('compose', help='generate a Spinal SoC with explicit bus and domain binders')
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
    return [ToolSpec('soc_compose', 'Generate an RV32 Spinal top with bus ingress bridges. Generation is not simulation evidence.',
                     schema({'source': {'type':'string'}, 'out': {'type':'string'}, 'elf': {'type':'string'}}, ['source','out']), execute, side_effects='writes generated artifacts and reports to out', native_tools=())]


def compose(source, out, elf=None):
    """Load the handler on first use."""
    from rvw.soc.compose import compose as implementation
    return implementation(source, out, elf)
