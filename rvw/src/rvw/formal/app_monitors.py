"""Additional generic safety monitors for explicit endpoint contracts."""

KINDS = ('onehot', 'mutex', 'array_bound', 'arithmetic_overflow', 'toggle', 'fifo')


def generate(prop, ports, signal, expr, clock, reset):
    kind = prop['kind']
    if kind == 'fifo':
        return fifo(prop, ports, signal, clock, reset)
    name = signal(prop['signal'])
    width = ports[name]['width']
    if kind in ('onehot', 'mutex'):
        zero = prop.get('allow_zero', kind == 'mutex')
        if type(zero) is not bool:
            raise ValueError('allow_zero must be a boolean')
        return [], f'(({name} & ({name} - {width}\'d1)) == 0)' + ('' if zero else f' && ({name} != 0)')
    if kind == 'array_bound':
        size = prop['size']
        if type(size) is not int or not 1 <= size <= 2**width:
            raise ValueError('array bound must fit the address width')
        return [], f'!({expr(prop.get("enable", "1"))}) || ({{1\'b0,{name}}} < {width+1}\'d{size})'
    if kind == 'arithmetic_overflow':
        other = signal(prop['other'])
        if ports[other]['width'] != width or prop.get('operation', 'add') not in ('add', 'sub'):
            raise ValueError('arithmetic operands need equal widths and add/sub operation')
        operation = prop.get('operation', 'add')
        symbol = '+' if operation == 'add' else '-'
        body = [f'wire [{width}:0] rvwa_extended = {{1\'b0,{name}}} {symbol} {{1\'b0,{other}}};']
        if type(prop.get('signed', False)) is not bool:
            raise ValueError('signed must be a boolean')
        if prop.get('signed', False):
            bad = (f'({name}[{width-1}] == {other}[{width-1}])' if operation == 'add' else
                   f'({name}[{width-1}] != {other}[{width-1}])')
            assertion = f'!({bad} && (rvwa_extended[{width-1}] != {name}[{width-1}]))'
        else:
            assertion = f'!rvwa_extended[{width}]'
        return body, f'!({expr(prop.get("enable", "1"))}) || ({assertion})'
    bit = prop['bit']
    if type(bit) is not int or not 0 <= bit < width:
        raise ValueError('toggle bit outside signal width')
    return [f'reg rvwa_previous, rvwa_seen = 0;',
            f'always @(posedge {clock}) begin rvwa_seen <= !{reset}; rvwa_previous <= {name}[{bit}]; end'], \
           f'!(rvwa_seen && ({name}[{bit}] != rvwa_previous))'


def fifo(prop, ports, signal, clock, reset):
    push, pop, data, output = (signal(prop[k]) for k in ('push', 'pop', 'write_data', 'read_data'))
    capacity = prop['capacity']
    width = ports[data]['width']
    if type(capacity) is not int or not 1 <= capacity <= 1024 or ports[output]['width'] != width or any(ports[p]['width'] != 1 for p in (push, pop)):
        raise ValueError('FIFO needs capacity 1..1024, one-bit events and equal data widths')
    body = [f'reg [{width-1}:0] rvwa_queue [0:{capacity-1}];',
            f'integer rvwa_read=0, rvwa_write=0, rvwa_count=0;',
            f'always @(posedge {clock}) begin',
            f' if ({reset}) begin rvwa_read<=0; rvwa_write<=0; rvwa_count<=0; end',
            ' else begin',
            f' if ({pop} && rvwa_count>0) begin',
            f'  assert({output} == rvwa_queue[rvwa_read]);',
            f'  rvwa_read <= rvwa_read == {capacity-1} ? 0 : rvwa_read+1; end',
            f' if ({push} && (rvwa_count<{capacity} || {pop})) begin',
            f'  rvwa_queue[rvwa_write] <= {data};',
            f'  rvwa_write <= rvwa_write == {capacity-1} ? 0 : rvwa_write+1; end',
            f' if ({push} && !{pop}) rvwa_count <= rvwa_count+1;',
            f' if ({pop} && !{push}) rvwa_count <= rvwa_count-1;',
            ' end end']
    return body, f'(!{pop} || rvwa_count>0) && (!{push} || {pop} || rvwa_count<{capacity})'
