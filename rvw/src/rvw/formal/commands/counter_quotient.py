"""Counter simulation-relation certificate command."""


def register(subparsers):
    from rvw.formal.counter_quotient import run
    p = subparsers.add_parser('counter-quotient', help='certify a smaller modulo counter against a typed concrete leaf')
    p.add_argument('--manifest', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--timeout', type=float, default=30)
    p.add_argument('--engine', default='abc:pdr')
    p.add_argument('--depth', type=int, default=12)
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=run)


def mcp_tools():
    from rvw.mcp.spec import ToolSpec, schema
    from rvw.formal.mcp_tools import _runner
    return [ToolSpec('formal_counter_quotient',
                    'Prove a reset-qualified modulo relation between a typed concrete counter and a smaller model.',
                    schema({'manifest': {'type': 'string'}, 'out': {'type': 'string'},
                            'engine': {'type': 'string'}, 'depth': {'type': 'integer', 'minimum': 2},
                            'timeout': {'type': 'number', 'exclusiveMinimum': 0}}, ['out', 'manifest']),
                    _runner('counter-quotient'), long=True, side_effects='long-running; writes generated artifacts and reports to out; launches selected native tools', native_tools=('Yosys', 'SymbiYosys', 'yosys-smtbmc', 'Yices', 'Z3', 'Boolector', 'Bitwuzla', 'CVC4', 'CVC5', 'MathSAT', 'ABC', 'suprove', 'Avy', 'rIC3', 'EBMC', 'pono', 'btormc', 'btorsim'))]
