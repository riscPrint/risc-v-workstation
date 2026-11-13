"""Translate a closed, bit-mapped Yosys design to C for CBMC.

One step evaluates combinational logic, then updates all registers together.
Only scalar positive-edge registers and Boolean gates are accepted.
"""
from .common import check_ident

GATES = {'$_NOT_', '$_AND_', '$_OR_', '$_XOR_', '$_XNOR_', '$_NAND_', '$_NOR_', '$_MUX_', '$_BUF_'}


def uncertainty(kind, values, unknown):
    """Conservative Boolean unknown propagation, including controlling values."""
    a, *rest = values
    ta, *tail = unknown
    b = rest[0] if rest else '0'
    tb = tail[0] if tail else '0'
    if kind in ('$_NOT_', '$_BUF_'):
        return ta
    if kind in ('$_XOR_', '$_XNOR_'):
        return f'({ta} || {tb})'
    if kind in ('$_AND_', '$_NAND_'):
        return f'(({ta} && ({tb} || {b})) || ({tb} && {a}))'
    if kind in ('$_OR_', '$_NOR_'):
        return f'(({ta} && ({tb} || !{b})) || ({tb} && !{a}))'
    if kind == '$_MUX_':
        select, ts = rest[1], tail[1]
        return f'(({select} ? {tb} : {ta}) || ({ts} && ({ta} || {tb} || ({a} != {b}))))'
    raise ValueError('unsupported gate uncertainty: '+kind)


def translate(design, width, latency, *, definedness=False):
    mod = design['modules']['dut']
    ports = mod['ports']
    expected = {'a': ('input', width), 'b': ('input', width), 'y': ('output', width)}
    optional = {'c': ('input', width), 'rm': ('input', 3), 'flags': ('output', 5)}
    if latency:
        expected.update({'clk': ('input', 1), 'reset': ('input', 1), 'start': ('input', 1), 'done': ('output', 1)})
    if set(ports) - set(expected) - set(optional) or set(expected) - set(ports):
        raise ValueError('unsupported DUT interface')
    for name, port in ports.items():
        direction, size = (expected | optional)[name]
        if port['direction'] != direction or len(port['bits']) != size or port.get('signed'):
            raise ValueError(f'bad port width or direction: {name}')
    if mod.get('memories') or mod.get('attributes', {}).get('blackbox'):
        raise ValueError('memory or blackbox is unsupported')
    cells = mod.get('cells', {}).values()
    registers, comb = [], []
    public_reset_values = {}
    for cell in cells:
        kind, c = cell['type'], cell['connections']
        if kind == '$_DFF_P_' and latency:
            if c['C'] != ports['clk']['bits']:
                raise ValueError('generated clocks are unsupported')
            registers.append((c['Q'][0], c['D'][0]))
        elif kind in ('$_DFF_PP0_', '$_DFF_PP1_') and latency:
            if c['C'] != ports['clk']['bits'] or c['R'] != ports['reset']['bits']:
                raise ValueError('asynchronous state needs the declared public clock and active-high reset')
            registers.append((c['Q'][0], c['D'][0]))
            public_reset_values[c['Q'][0]] = int(kind == '$_DFF_PP1_')
        elif kind in GATES:
            if latency and any(ports['clk']['bits'][0] in bits for bits in c.values()):
                raise ValueError('clock used as data is unsupported')
            comb.append(cell)
        else:
            raise ValueError(f'unsupported mapped cell: {kind}')
    if any('init' in n.get('attributes', {}) for n in mod['netnames'].values()):
        raise ValueError('use explicit reset, not init attributes')
    bits = {b for p in ports.values() for b in p['bits'] if isinstance(b, int)}
    bits.update(b for cell in cells for conn in cell['connections'].values() for b in conn if isinstance(b, int))
    def v(b):
        if isinstance(b, int):
            return f'n{b}'
        if b not in ('0', '1'):
            if definedness and b in ('x', 'z'):
                return 'nondet_bool()'
            raise ValueError('X/Z constants are unsupported')
        return b
    def u(b):
        return f'u{b}' if isinstance(b, int) else ('1' if b in ('x', 'z') else '0')
    available = {'0', '1', 'x', 'z'} if definedness else {'0', '1'}
    driven = set()
    lines = ['#include <stdint.h>', 'extern _Bool nondet_bool(void);',
             'extern uint64_t nondet_u64(void);', 'extern void __CPROVER_assert(_Bool, const char *);',
             'extern void __CPROVER_assume(_Bool);']
    lines += [f'static _Bool n{b};' for b in sorted(bits)]
    if definedness:
        lines += [f'static _Bool u{b};' for b in sorted(bits)]
    for name, port in ports.items():
        check_ident('port', name)
        if port['direction'] == 'input':
            for b in port['bits']:
                if not isinstance(b, int) or b in driven:
                    raise ValueError('aliased input')
                available.add(b); driven.add(b)
    for q, d in registers:
        if q in driven:
            raise ValueError('multiple state drivers')
        available.add(q); driven.add(q)
    statements = []
    while comb:
        pending = []
        for cell in comb:
            c, kind = cell['connections'], cell['type']
            args = [c[p][0] for p in ('A', 'B', 'S') if p in c]
            if not all(b in available for b in args):
                pending.append(cell); continue
            y = c['Y'][0]
            if y in driven or not isinstance(y, int):
                raise ValueError('multiple drivers or constant output driver')
            a = v(args[0]); b = v(args[1]) if len(args)>1 else '0'
            expr = {'$_NOT_': f'!{a}', '$_BUF_': a, '$_AND_': f'{a} & {b}',
                    '$_OR_': f'{a} | {b}', '$_XOR_': f'{a} ^ {b}',
                    '$_XNOR_': f'!({a} ^ {b})', '$_NAND_': f'!({a} & {b})',
                    '$_NOR_': f'!({a} | {b})',
                    '$_MUX_': f'{v(args[2])} ? {b} : {a}' if len(args)>2 else '0'}[kind]
            statements.append(f'{v(y)} = {expr};')
            if definedness:
                statements.append(f'{u(y)} = {uncertainty(kind, [v(x) for x in args], [u(x) for x in args])};')
            available.add(y); driven.add(y)
        if len(pending) == len(comb):
            raise ValueError('combinational loop or undriven input')
        comb = pending
    if bits - driven:
        raise ValueError('undriven net bits')
    reset_statements = []
    for q, value in public_reset_values.items():
        reset_statements.append(f'if ({v(ports["reset"]["bits"][0])}) {{ {v(q)} = {value};' +
                                (f' {u(q)} = 0;' if definedness else '') + ' }')
    lines += ['static void eval(void) {'] + reset_statements + statements + ['}']
    lines += ['static void tick(void) {', 'eval();']
    lines += [f'_Bool next{i} = {v(d)};' for i, (q,d) in enumerate(registers)]
    if definedness:
        lines += [f'_Bool next_unknown{i} = {u(d)};' for i, (q,d) in enumerate(registers)]
    lines += [f'{v(q)} = next{i};' for i, (q,d) in enumerate(registers)]
    if definedness:
        lines += [f'{u(q)} = next_unknown{i};' for i, (q,d) in enumerate(registers)]
    lines += ['eval();', '}']
    lines += ['static void init(void) {'] + [f'{v(q)} = nondet_bool();' for q,d in registers] + ['}']
    def put(name, expr):
        return [f'{v(b)} = (({expr}) >> {i}) & 1;' for i,b in enumerate(ports[name]['bits'])]
    def get(name):
        return '(' + ' | '.join(f'((uint64_t){v(b)} << {i})' for i,b in enumerate(ports[name]['bits'])) + ')'
    translated = ('\n'.join(lines)+'\n', ports, put, get)
    if definedness:
        def unknown(name):
            return '('+' || '.join(u(b) for b in ports[name]['bits'])+')'
        return (*translated, unknown)
    return translated
