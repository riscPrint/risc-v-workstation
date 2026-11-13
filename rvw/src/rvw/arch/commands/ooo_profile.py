"""PC region timing profiles and configuration differences."""
import json
from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import run_function


def execute(action, **kw):
    from rvw.ooo.regions import profile, compare
    return (profile if action == 'ooo-profile' else compare)(**kw)


def command(args):
    kw = vars(args).copy()
    for key in ('func', 'command', 'arch_action', 'json'):
        kw.pop(key, None)
    try:
        result = execute(args.arch_action, **kw)
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps({'error': str(exc)}))
        return 2


def register(sub):
    p = sub.add_parser('ooo-profile', help='attribute model slots to ELF symbols or PC regions')
    p.add_argument('config'); p.add_argument('trace')
    g = p.add_mutually_exclusive_group()
    g.add_argument('--elf'); g.add_argument('--regions')
    p.add_argument('--max-cycles', type=int, default=1000000)
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=command)
    p = sub.add_parser('ooo-diff', help='compare two saved model profiles')
    p.add_argument('base'); p.add_argument('candidate')
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=command)


def mcp_tools():
    tools = []
    for action, fields in [('ooo-profile', ('config','trace')), ('ooo-diff', ('base','candidate'))]:
        props = {k: {'type':'string'} for k in fields}
        if action == 'ooo-profile':
            props.update(elf={'type':'string'}, regions={'type':'string'},
                         max_cycles={'type':'integer', 'minimum':1})
        def handler(job, _action=action, **kw):
            return run_function(job, __name__, 'execute', dict(action=_action, **kw))
        tools.append(ToolSpec('arch_'+action.replace('-','_'), 'Model slot estimates; accuracy inconclusive.',
                              schema(props, list(fields)), handler, long=True))
    return tools
