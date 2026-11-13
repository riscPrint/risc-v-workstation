"""CLI and MCP entry points for unbounded instruction-check portfolios."""
import json
from pathlib import Path


def main(args):
    from rvw.common.project import load_project
    from rvw.formal.riscv_proof import run
    from rvw.formal.common import sigterm_raises
    try:
        project = load_project(getattr(args, 'project', None))
        if project is None:
            raise ValueError('select a riscv_formal project')
        cfg = dict(project.sections['riscv_formal'])
        if args.checks:
            cfg['checks'] = args.checks.split(',') + ['cover']
            cfg['check_options'] = {k:v for k,v in cfg.get('check_options', {}).items() if k in cfg['checks']}
        with sigterm_raises():
            result = run(cfg, Path(args.out), args.engines.split(','), args.timeout)
        print(json.dumps(result) if args.json else str(Path(args.out) / 'result.json'))
        return 1 if result['status'] == 'fail' else 3
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps(dict(status='error', error=str(exc))))
        return 2


def register(subparsers):
    p = subparsers.add_parser('riscv-proof', help='run upstream unbounded instruction checkers through engine-race')
    p.add_argument('--out', required=True)
    p.add_argument('--checks', help='comma-separated instruction checks; default: project selection')
    p.add_argument('--engines', default='abc:pdr,smtbmc:yices')
    p.add_argument('--timeout', type=float, default=180)
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=main)


def mcp_tools():
    from rvw.mcp.spec import ToolSpec, schema
    return [ToolSpec('formal_riscv_proof', 'Run unbounded RVFI instruction checks with the native engine portfolio.',
                    schema({'project': {'type':'string'}, 'out': {'type':'string'}, 'checks': {'type':'string'},
                            'engines': {'type':'string'}, 'timeout': {'type':'number', 'exclusiveMinimum':0}}, ['out']),
                    mcp_run, long=True, side_effects='writes-files', native_tools=('Yosys', 'SymbiYosys', 'yosys-smtbmc', 'Yices', 'Z3', 'Boolector', 'Bitwuzla', 'CVC4', 'CVC5', 'MathSAT', 'ABC', 'suprove', 'Avy', 'rIC3', 'EBMC', 'pono', 'btormc', 'btorsim'))]


def mcp_run(job, **args):
    from rvw.formal.mcp_tools import _argv
    from rvw.mcp.spec import ToolError
    code=job.run(_argv('riscv-proof',args))
    if code not in (1,3):
        raise ToolError('instruction proof failed to run',{'exit_code':code,'log_tail':job.tail(30)})
    result=json.loads((Path(args['out'])/'result.json').read_text())
    if result.get('schema')!='rvw.riscv-proof/1' or result.get('status')!={1:'fail',3:'inconclusive'}[code]:
        raise ToolError('invalid instruction proof result')
    return result
