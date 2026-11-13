"""Value-sensitive Boolean IFT instrumentation of a Yosys simplemap netlist."""
import re
from .unsupported import UnsupportedSecurity, RESET_HINT, check_properties


def instrument(design, top, *, state_sources=()):
    """Return Verilog with a taint port for each data port. Refuse unknown cells.

    Each taint bit means that either value is possible at that bit. Gate transfer
    functions enumerate those possibilities. Reconvergent correlations can be lost.
    Clock is public. State starts unknown; the caller must apply a public reset.
    """
    mod = design['modules'][top]
    if mod.get('memories') or mod.get('attributes', {}).get('blackbox'):
        raise ValueError('memories and blackboxes are unmodeled')
    if any('init' in d.get('attributes', {}) for d in mod['netnames'].values()):
        raise ValueError('initial state attributes are unmodeled; use public reset')
    ports = mod['ports']
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', top):
        raise ValueError('simple top identifier required')
    if any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', p) or p.endswith('__t') for p in ports):
        raise ValueError('simple port identifiers without __t suffix required')
    check_properties(mod)
    cells = mod.get('cells', {})
    supported = {'$_NOT_', '$_AND_', '$_OR_', '$_XOR_', '$_MUX_', '$_DFF_P_'}
    bad = sorted({c['type'] for c in cells.values()} - supported)
    if any(kind.startswith('$_DFF_') and kind != '$_DFF_P_' for kind in bad):
        raise UnsupportedSecurity('unsupported reset or clock in IFT shadow pass. ' + RESET_HINT)
    if bad:
        raise ValueError(f'unmodeled cells: {bad}')
    state = {c['connections']['Q'][0] for c in cells.values() if c['type'] == '$_DFF_P_'}
    source_bits = set()
    if len(set(state_sources)) != len(state_sources):
        raise ValueError('distinct internal state sources required')
    for name in state_sources:
        net = mod['netnames'].get(name)
        if not net or not net['bits'] or any(type(b) is not int or b not in state for b in net['bits']):
            raise ValueError('internal source must name synchronous register Q bits: ' + name)
        source_bits.update(net['bits'])
    clocks = {c['connections']['C'][0] for c in cells.values() if c['type'] == '$_DFF_P_'}
    if len(clocks) > 1:
        raise ValueError('one public rising-edge clock required')
    clock_ports = {p for p, d in ports.items() if d['direction'] == 'input' and d['bits'] == list(clocks)} if clocks else set()
    if clocks and len(clock_ports) != 1:
        raise ValueError('clock must be a scalar public input port')
    # Yosys can retain unused slices of temporary vector netnames. Only live
    # port/cell bits need drivers; live undriven inputs still fail below.
    bits = {b for d in ports.values() for b in d['bits'] if isinstance(b, int)}
    bits.update(b for c in cells.values() for values in c['connections'].values() for b in values if isinstance(b, int))
    port_names = {name for p in ports for name in (p, p + '__t')}
    prefix = ''
    while any(f'{prefix}{kind}{b}' in port_names for kind in ('n', 't') for b in bits):
        prefix += '_'
    def v(b):
        if isinstance(b, int):
            return f'{prefix}n{b}'
        if b in ('x', 'z'):
            return "1'b0"  # Representative value; t(b)=1 admits both Boolean values.
        if b not in ('0', '1'):
            raise ValueError('X/Z constants are unmodeled')
        return f"1'b{b}"
    def t(b):
        if b in source_bits:
            return "1'b1"
        return f'{prefix}t{b}' if isinstance(b, int) else ("1'b1" if b in ('x', 'z') else "1'b0")
    names = [n for p in ports for n in ([p] if p in clock_ports else [p, p+'__t'])]
    lines = [f'module {top}__ift({", ".join(names)});']
    for p, d in ports.items():
        if d['direction'] not in ('input', 'output'):
            raise ValueError('inout ports are unmodeled')
        for n in ([p] if p in clock_ports else [p, p+'__t']):
            lines.append(f'{d["direction"]} [{len(d["bits"])-1}:0] {n};')
    for b in sorted(bits):
        shadow = '' if b in source_bits else f', {prefix}t{b}'
        lines.append(f'{"reg" if b in state else "wire"} {prefix}n{b}{shadow};')
    driven = set()
    for p, d in ports.items():
        for i, b in enumerate(d['bits']):
            if d['direction'] == 'input':
                if not isinstance(b, int) or b in driven:
                    raise ValueError('aliased input bits are unmodeled')
                driven.add(b)
                lines += [f'assign {v(b)} = {p}[{i}];', f'assign {t(b)} = ' + ("1'b0;" if p in clock_ports else f'{p}__t[{i}];')]
            else:
                lines += [f'assign {p}[{i}] = {v(b)};', f'assign {p}__t[{i}] = {t(b)};']
    for c in cells.values():
        kind, con = c['type'], c['connections']
        out = con['Q' if kind == '$_DFF_P_' else 'Y'][0]
        if out in driven:
            raise ValueError('multiple drivers are unmodeled')
        driven.add(out)
        if kind == '$_DFF_P_':
            d, clk = con['D'][0], con['C'][0]
            shadow = '' if out in source_bits else f' {t(out)} <= {t(d)};'
            lines.append(f'always @(posedge {v(clk)}) begin {v(out)} <= {v(d)};{shadow} end')
            continue
        args = [con[p][0] for p in ('A', 'B', 'S') if p in con]
        a = v(args[0])
        expr = {'$_NOT_': lambda: f'~{a}', '$_AND_': lambda: f'{a} & {v(args[1])}',
                '$_OR_': lambda: f'{a} | {v(args[1])}', '$_XOR_': lambda: f'{a} ^ {v(args[1])}',
                '$_MUX_': lambda: f'{v(args[2])} ? {v(args[1])} : {a}'}[kind]()
        lines.append(f'assign {v(out)} = {expr};')
        # Taint is possible output 0 AND possible output 1. This includes control taint.
        possible = {0: [], 1: []}
        from itertools import product
        for values in product((0, 1), repeat=len(args)):
            x = values[0]
            y = values[1] if len(values) > 1 else 0
            z = values[2] if len(values) > 2 else 0
            result = {'$_NOT_': 1-x, '$_AND_': x & y, '$_OR_': x | y,
                      '$_XOR_': x ^ y, '$_MUX_': y if z else x}[kind]
            terms = [f'({t(b)} | {v(b) if val else "~"+v(b)})' for b, val in zip(args, values)]
            possible[result].append('(' + ' & '.join(terms) + ')')
        lines.append(f'assign {t(out)} = ({" | ".join(possible[0])}) & ({" | ".join(possible[1])});')
    if bits - driven:
        raise ValueError(f'undriven bits are unmodeled: {sorted(bits-driven)}')
    return '\n'.join(lines + ['endmodule', ''])
