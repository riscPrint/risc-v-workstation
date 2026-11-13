"""Single-step debug state comparison with Spike."""
import json


def register(sub):
    p = sub.add_parser('state-compare', help='compare GPRs, selected CSRs and DPC at RTL step halts with Spike')
    for name in ('profile', 'elf', 'platform', 'shim', 'out'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--steps', type=int, default=16)
    p.add_argument('--csr', dest='csrs', action='append')
    p.add_argument('--port', type=int)
    p.set_defaults(func=_cli)


def _cli(args):
    from rvw.debug.state_compare import run
    result = run(**{k: getattr(args, k) for k in ('profile', 'elf', 'platform', 'shim', 'out', 'steps', 'csrs', 'port')})
    print(json.dumps(result))
    return 0 if result['status'] == 'match' else 1


def _run(job, **kwargs):
    from rvw.mcp.worker import run_function
    return run_function(job, 'rvw.debug.state_compare', 'run', kwargs)


def mcp_tools():
    from rvw.mcp.spec import ToolSpec, schema
    string = {'type': 'string'}
    return [ToolSpec('debug_state_compare', 'Compare all GPRs, DPC and selected CSRs at RTL step halts with native Spike. Changes target state.',
        schema({**{k: string for k in ('out', 'profile', 'elf', 'platform', 'shim')},
                'steps': {'type': 'integer', 'minimum': 1}, 'csrs': {'type': 'array', 'items': string},
                'port': {'type': 'integer'}}, ['out', 'profile', 'elf', 'platform', 'shim']), _run, long=True, side_effects='loads ELF into target RAM; writes GPRs, CSRs and DPC; writes C3 results.json', native_tools=('Spike',))]
