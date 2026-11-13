"""Bind a project module's declared ports to the datapath reference interface."""
from copy import deepcopy
from .common import check_ident


def bind(design, spec):
    top = spec['top']
    check_ident('binding top', top)
    module = deepcopy(design['modules'][top])
    constants = spec.get('constants', {})
    if not isinstance(constants, dict):
        raise ValueError('binding constants must be a port-to-integer map')
    replacements = {}
    for name, value in constants.items():
        port = module['ports'].get(name)
        if port is None or port['direction'] != 'input' or type(value) is not int or not 0 <= value < 1 << len(port['bits']):
            raise ValueError('binding constants need input ports and fitting unsigned values')
        for index, bit in enumerate(port['bits']):
            if not isinstance(bit, int) or bit in replacements:
                raise ValueError('aliased constant input bits are unsupported')
            replacements[bit] = str((value >> index) & 1)
    def bits(values):
        return [replacements.get(bit, bit) for bit in values]
    for name in constants:
        del module['ports'][name]
    if replacements:
        for port in module['ports'].values():
            port['bits'] = bits(port['bits'])
        for cell in module.get('cells', {}).values():
            cell['connections'] = {name: bits(values) for name, values in cell['connections'].items()}
        for net in module.get('netnames', {}).values():
            net['bits'] = bits(net['bits'])
    aliases = spec['ports']
    canonical = {'clk', 'reset', 'start', 'done', 'a', 'b', 'c', 'rm', 'y', 'flags'}
    if not isinstance(aliases, dict) or not set(aliases) <= canonical:
        raise ValueError('binding ports must use canonical datapath names')
    for name in aliases.values():
        check_ident('binding port', name)
    if len(set(aliases.values())) != len(aliases) or set(aliases.values()) - set(module['ports']):
        raise ValueError('binding needs distinct existing ports')
    inverse = {actual: name for name, actual in aliases.items()}
    ports = {inverse.get(name, name): port for name, port in module['ports'].items()}
    if len(ports) != len(module['ports']):
        raise ValueError('binding port names collide')
    unused = spec.get('unused_inputs', {})
    if not isinstance(unused, dict) or set(unused) - {'b', 'c'}:
        raise ValueError('unused_inputs can declare only reference b and c arguments')
    input_widths = spec.get('input_widths', {})
    output_widths = spec.get('output_widths', {})
    if not isinstance(input_widths, dict) or set(input_widths) - {'a','b','c'}:
        raise ValueError('input_widths supports only reference operand ports')
    if not isinstance(output_widths, dict) or set(output_widths) - {'y'}:
        raise ValueError('output_widths supports only the reference result port')
    if unused or input_widths:
        identifiers = [bit for p in module['ports'].values() for bit in p['bits'] if isinstance(bit, int)]
        identifiers += [bit for cell in module.get('cells', {}).values() for values in cell['connections'].values() for bit in values if isinstance(bit, int)]
        identifiers += [bit for net in module.get('netnames', {}).values() for bit in net['bits'] if isinstance(bit, int)]
        next_bit = max(identifiers, default=1) + 1
        for name, width in unused.items():
            if name in ports or type(width) is not int or not 1 <= width <= 64:
                raise ValueError('unused reference inputs need fresh names and widths 1..64')
            ports[name] = {'direction':'input', 'bits':list(range(next_bit,next_bit+width))}
            next_bit += width
        for name, width in input_widths.items():
            port = ports.get(name)
            if port is None or port['direction'] != 'input' or type(width) is not int or not len(port['bits']) <= width <= 64:
                raise ValueError('input widening needs existing input ports and widths up to 64; truncation is refused')
            count = width - len(port['bits'])
            port['bits'] = [*port['bits'], *range(next_bit,next_bit+count)]
            next_bit += count
    for name, width in output_widths.items():
        port = ports.get(name)
        if port is None or port['direction'] != 'output' or type(width) is not int or not len(port['bits']) <= width <= 64:
            raise ValueError('output widening needs an existing result port and width up to 64; truncation is refused')
        port['bits'] = [*port['bits'], *(['0']*(width-len(port['bits'])))]
    # The translator checks every port, bit width, state cell and driver after
    # this rename. Only declared constant inputs are removed. Other ports remain obligations.
    return {'modules': {'dut': {**module, 'ports': ports}}}
