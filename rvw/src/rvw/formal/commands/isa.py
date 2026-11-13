"""ISA kit front command and MCP entry point."""
import json
from pathlib import Path


def main(args):
    from rvw.common.project import load_project
    from rvw.formal.common import sigterm_raises
    from rvw.formal.isa import run, table
    try:
        project = load_project(getattr(args, 'project', None))
        if project is None:
            raise ValueError('select a project with --project')
        cfg = project.sections.get('riscv_formal')
        if cfg and cfg.get('build'):
            from rvw.common.proc import run_group
            built = run_group(['nice', '-n', '10', *cfg['build']], cwd=project.root,
                              timeout=120, capture=True, text=True)
            if built.returncode or built.timed_out:
                raise ValueError('riscv_formal.build failed: ' + (built.stderr or built.stdout)[-1500:])
        with sigterm_raises():
            result = run(project.sections.get('riscv_formal'), args.out, args.timeout,
                         project.name, unbounded=args.unbounded, engines=args.engines.split(','), machine=args.machine, abstraction=args.abstraction)
        print(json.dumps(result) if args.json else table(result))
        return 1 if result['status'] == 'fail' else 3
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps(dict(status='error', error=str(exc))))
        return 2


def register(subparsers):
    p = subparsers.add_parser('isa', help='run the ISA proof kit and print its scoped signoff table')
    p.add_argument('--out', required=True)
    p.add_argument('--abstraction', help='single-flight RAM abstraction manifest')
    p.add_argument('--machine', help='machine-checks manifest for the same project RTL')
    p.add_argument('--timeout', type=float, default=110)
    p.add_argument('--unbounded', action='store_true')
    p.add_argument('--engines', default='abc:pdr')
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=main)


def mcp_run(job, **args):
    from rvw.formal.mcp_tools import _argv
    from rvw.mcp.spec import ToolError
    code = job.run(_argv('isa', args))
    if code not in (1, 3):
        raise ToolError('ISA kit failed to run', {'exit_code': code, 'log_tail': job.tail(30)})
    report = json.loads((Path(args['out']) / 'result.json').read_text())
    if report.get('schema') != 'rvw.isa-signoff/1' or report.get('status') != {1:'fail', 3:'inconclusive'}[code]:
        raise ToolError('ISA kit result does not match its exit code')
    return report


def mcp_tools():
    from rvw.mcp.spec import ToolSpec, schema
    return [ToolSpec('formal_isa', 'Run the ISA kit. Return per-check bounds, failures and unsupported gaps.',
                     schema({'project': {'type':'string'}, 'out': {'type':'string'}, 'machine': {'type':'string'}, 'abstraction': {'type':'string'}, 'timeout': {'type':'number', 'exclusiveMinimum':0},
                             'unbounded': {'type':'boolean'}, 'engines': {'type':'string'}}, ['out']),
                     mcp_run, long=True, side_effects='writes-files', native_tools=('Yosys', 'SymbiYosys', 'yosys-smtbmc', 'Yices', 'Z3', 'Boolector', 'Bitwuzla', 'CVC4', 'CVC5', 'MathSAT', 'ABC', 'suprove', 'Avy', 'rIC3', 'EBMC', 'pono', 'btormc', 'btorsim'))]
