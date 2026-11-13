"""Conservative transition-cone identities for named RTL state predicates."""
from hashlib import sha256
import json


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def identity(module, roots):
    drivers, public, initial, ports = {}, {}, {}, {}
    for name, net in module.get('netnames', {}).items():
        init = net.get('attributes', {}).get('init', '')
        for i, bit in enumerate(net['bits']):
            if not net.get('hide_name', 0) and not name.startswith('$') and not net.get('offset', 0) and not net.get('upto', 0):
                public.setdefault(bit, []).append((name, i))
            if init and isinstance(bit, int):
                value = init[-1 - i] if i < len(init) else 'x'
                if bit in initial and initial[bit] != value:
                    raise ValueError('conflicting state initialization')
                initial[bit] = value
    for name, port in module['ports'].items():
        if port['direction'] == 'input':
            for i, bit in enumerate(port['bits']):
                ports[bit] = (name, i, len(port['bits']))
    for name, cell in module['cells'].items():
        for port, direction in cell['port_directions'].items():
            if direction == 'output':
                for i, bit in enumerate(cell['connections'][port]):
                    if isinstance(bit, int):
                        if bit in drivers:
                            raise ValueError('multiple drivers in lemma cone')
                        drivers[bit] = (name, port, i)
    expressions, registers, pending, memo, active = {}, {}, [], {}, set()
    def named(bit):
        if bit not in public:
            raise ValueError('lemma cone has unnamed state')
        name, offset = min(public[bit])
        return f'{name}[{offset}]'
    def expression(bit):
        if bit in memo:
            return memo[bit]
        if bit in active:
            raise ValueError('combinational loop in lemma cone')
        active.add(bit)
        if isinstance(bit, str):
            record = ['constant', bit]
        elif bit in ports:
            record = ['input', *ports[bit]]
        elif bit not in drivers:
            raise ValueError('undriven bit in lemma cone')
        else:
            name, port, offset = drivers[bit]
            cell = module['cells'][name]
            kind = cell['type']
            if kind in ('$dff', '$dffe', '$adff', '$adffe', '$sdff', '$sdffe', '$sdffce', '$ff'):
                if port != 'Q':
                    raise ValueError('unexpected sequential output')
                record = ['state', named(bit)]
                if name not in registers:
                    registers[name] = None
                    pending.append(name)
            else:
                if 'mem' in kind or kind in ('$dlatch', '$adlatch', '$sr') or not kind.startswith('$'):
                    raise ValueError('unsupported cell in lemma cone')
                inputs = {p: [expression(b) for b in cell['connections'][p]]
                          for p, direction in sorted(cell['port_directions'].items()) if direction == 'input'}
                record = ['cell', kind, cell.get('parameters', {}), port, offset, inputs]
                # Keep nondeterministic cells distinct, including cross-bit correlation.
                if kind.startswith('$any') or kind.startswith('$all'):
                    record.append(name)
        active.remove(bit)
        key = digest(record)
        expressions[key] = record
        memo[bit] = key
        return key
    root_bits = []
    for name, offset in roots:
        net = module['netnames'].get(name, {})
        if net.get('offset', 0) or net.get('upto', 0):
            raise ValueError('lemma signals require zero-based descending ranges')
        bits = net.get('bits', [])
        if not 0 <= offset < len(bits):
            raise ValueError('lemma signal or bit is missing')
        root_bits.append(expression(bits[offset]))
    state_records = {}
    while pending:
        name = pending.pop()
        cell = module['cells'][name]
        q = cell['connections']['Q']
        names = [named(b) for b in q]
        inputs = {p: [expression(b) for b in cell['connections'][p]]
                  for p, direction in sorted(cell['port_directions'].items()) if direction == 'input'}
        record = {'type': cell['type'], 'parameters': cell.get('parameters', {}),
                  'state': names, 'initial': [initial.get(b, 'x') for b in q], 'inputs': inputs}
        # A stable named state replaces generated cell names and numeric bit ids.
        key = tuple(names)
        state_records['|'.join(key)] = record
        registers[name] = record
    record = {'schema': 'rvw.formal-lemma-cone/1', 'roots': root_bits,
              'state': state_records, 'expressions': expressions}
    return digest(record), record
