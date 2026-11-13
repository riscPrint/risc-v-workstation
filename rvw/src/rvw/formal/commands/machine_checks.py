"""Generate and run project-bound machine transition properties."""
import json
from pathlib import Path


def main(args):
    from rvw.formal.machine_checks import generate, run
    try:
        path = Path(args.manifest).resolve()
        plan = json.loads(path.read_text())
        result = (run(plan, path.parent, args.out, args.timeout) if args.run else
                  generate(plan, path.parent, args.out))
        print(json.dumps(result) if args.json else str(Path(args.out)/'result.json'))
        return 1 if result['status'] == 'fail' else 3 if args.run else 0
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps(dict(status='error', error=str(exc))))
        return 2


def register(subparsers):
    p = subparsers.add_parser('machine-checks', help='generate RV32 machine-transition properties from project observations')
    p.add_argument('--manifest', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--run', action='store_true')
    p.add_argument('--timeout', type=float, default=110)
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=main)


def mcp_run(job, **args):
    from rvw.formal.mcp_tools import _argv
    from rvw.mcp.spec import ToolError
    code = job.run(_argv('machine-checks', args))
    if code not in (0, 1, 3):
        raise ToolError('machine checks failed to run', {'exit_code':code, 'log_tail':job.tail(30)})
    return json.loads((Path(args['out'])/'result.json').read_text())


def mcp_tools():
    from rvw.mcp.spec import ToolSpec, schema
    return [ToolSpec('formal_machine_checks', 'Generate project-bound RV32 machine transition properties and optionally run bounded checks.',
                     schema({'manifest':{'type':'string'}, 'out':{'type':'string'}, 'run':{'type':'boolean'},
                             'timeout':{'type':'number', 'exclusiveMinimum':0}}, ['manifest','out']), mcp_run, long=True, side_effects='long-running; writes generated artifacts and reports to out; launches selected native tools', native_tools=('Yosys', 'SymbiYosys', 'yosys-smtbmc', 'Yices', 'Z3', 'Boolector', 'Bitwuzla', 'CVC4', 'CVC5', 'MathSAT', 'ABC', 'suprove', 'Avy', 'rIC3', 'EBMC', 'pono', 'btormc', 'btorsim'))]
