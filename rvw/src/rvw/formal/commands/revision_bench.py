"""Revision re-proof timing experiment."""
import json
from pathlib import Path


def run(args):
    from rvw.formal.revision_bench import measure
    base=Path(args.base).resolve();revised=Path(args.revised).resolve()
    # Resolve both manifests' source paths before choosing one common root.
    def load(path):
        plan=json.loads(path.read_text())
        for source in plan['sources']:
            source['path']=str((path.parent/source['path']).resolve())
        return plan
    out=Path(args.out)
    r=measure(load(base),load(revised),Path.cwd(),out,timeout=args.timeout,trials=args.trials)
    (out/'result.json').write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps(r) if args.json else str(out/'result.json'))
    return 0 if r['status']=='pass' else 1


def register(subparsers):
    p=subparsers.add_parser('revision-bench',help='measure cone-matched lemma reuse after a source revision')
    p.add_argument('--base',required=True)
    p.add_argument('--revised',required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--timeout',type=float,default=10)
    p.add_argument('--trials',type=int,default=3)
    p.add_argument('--json',action='store_true')
    p.set_defaults(func=run)


def mcp_tools():
    from rvw.mcp.spec import ToolSpec,schema
    from rvw.formal.mcp_tools import _runner
    return [ToolSpec('formal_revision_bench','Measure fresh re-proofs with cone-matched lemmas. Report signed time saved.',
        schema({'base':{'type':'string'},'revised':{'type':'string'},'out':{'type':'string'},
                'timeout':{'type':'number','exclusiveMinimum':0},'trials':{'type':'integer','minimum':1,'maximum':20}},
               ['base','revised','out']),_runner('revision-bench'),long=True, side_effects='long-running; writes generated artifacts and reports to out; launches selected native tools', native_tools=('Yosys', 'SymbiYosys', 'yosys-smtbmc', 'Yices', 'Z3', 'Boolector', 'Bitwuzla', 'CVC4', 'CVC5', 'MathSAT', 'ABC', 'suprove', 'Avy', 'rIC3', 'EBMC', 'pono', 'btormc', 'btorsim'))]
