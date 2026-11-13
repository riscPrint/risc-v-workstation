"""Prove one Boolean two-clock implication under global-step sampling."""
def run(args):
    from rvw.formal.cross_proof import run as execute
    return execute(args)


def register(subparsers):
    p = subparsers.add_parser('cross-prove', help='check two-clock Boolean implication with explicit global-step semantics')
    p.add_argument('--source', required=True)
    p.add_argument('--top', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--depth', type=int, default=20)
    p.add_argument('--timeout', type=float, default=60)
    p.add_argument('--engine', choices=['smtbmc:yices','smtbmc:z3','abc:pdr'], default='smtbmc:yices')
    p.add_argument('--mode', choices=['bmc','prove'], default='bmc')
    p.add_argument('--proof-cache')
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=run)


def mcp_tools():
    from rvw.formal.mcp_tools import _runner
    from rvw.mcp.spec import ToolSpec, schema
    return [ToolSpec('formal_cross_prove', 'Check a Boolean two-clock implication. Global samples, pre-update values; no clock fairness or between-sample event claim.',
        schema({'source':{'type':'string'}, 'top':{'type':'string'}, 'out':{'type':'string'},
                'depth':{'type':'integer','minimum':1}, 'timeout':{'type':'number','exclusiveMinimum':0},
                'mode':{'type':'string','enum':['bmc','prove']},
                'engine':{'type':'string','enum':['smtbmc:yices','smtbmc:z3','abc:pdr']},
                'proof_cache':{'type':'string'}}, ['source','top','out']),
        _runner('cross-prove'), long=True, side_effects='runs native formal jobs; writes generated models, C3 and JUnit under out',
        native_tools=('Yosys','SymbiYosys','yosys-smtbmc','Yices','Z3','ABC'))]
