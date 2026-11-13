"""Generate bounded, byte-addressed RAM environments from explicit bus bindings."""
import re


def render(cfg):
    memory = cfg.get('memory')
    if memory is None:
        return ''
    if not isinstance(memory, dict):
        raise ValueError('memory must be a contract table')
    if set(memory) - {'protocol', 'initial', 'response_cycles', 'address_width', 'reads', 'writes'}:
        raise ValueError('unknown memory contract field')
    if (memory.get('protocol') != 'combinational-byte' or
            memory.get('initial') != 'symbolic-stable' or
            type(memory.get('response_cycles')) is not int or memory['response_cycles'] != 0):
        raise ValueError('memory requires combinational-byte, response_cycles=0, initial=symbolic-stable')
    width = memory.get('address_width', 32)
    if type(width) is not int or not 1 <= width <= 64:
        raise ValueError('memory address_width must be 1..64')
    reads = memory.get('reads', [])
    writes = memory.get('writes', [])
    if not isinstance(reads, list) or not isinstance(writes, list) or not reads or len(writes) != 1:
        raise ValueError('memory needs reads and exactly one write port')
    for port in [*reads, *writes]:
        if not isinstance(port, dict) or set(port) != {'address', 'data', 'mask'} or any(
            not isinstance(v, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_$]*', v)
            for v in port.values()
        ):
            raise ValueError('memory ports need address, data and mask wrapper wire identifiers')
    # Retain all observations through the last assertion cycle. Overflow is an
    # assertion, never an assumption that can hide DUT behavior in longer proofs.
    depth = max([cfg['depth'], *[o.get('cycles', [cfg['depth']])[-1]
                                  for o in cfg.get('check_options', {}).values()]]) + 1
    ports = [*reads, *writes]
    lines = ['integer rvw_mem_count = 0;',
             'always @(posedge clock) begin',
             ' if (reset) rvw_mem_count <= 0;',
             f' else begin assert(rvw_mem_count < {depth});',
             f' if (rvw_mem_count < {depth}) rvw_mem_count <= rvw_mem_count + 1;',
             ' end', 'end']
    for n, port in enumerate(ports):
        for field, bits in [('address', width), ('data', 32), ('mask', 4)]:
            name = f'rvw_mem_{n}_{field}'
            lines += [f'reg [{bits-1}:0] {name} [0:{depth-1}];',
                      'always @(posedge clock)',
                      f' if (!reset && rvw_mem_count < {depth}) {name}[rvw_mem_count] <= {port[field]};']
    for n, port in enumerate(reads):
        for lane in range(4):
            value = f'{port["data"]}[{8*lane} +: 8]'
            addr = f'({port["address"]} + {width}\'d{lane})'
            expected = f'rvw_mem_expected_{n}_{lane}'
            lines += [f'reg [7:0] {expected};', 'always @* begin', f' {expected} = {value};',
                      f' for (integer h=0; h<{depth}; h=h+1) begin',
                      '  if (h < rvw_mem_count) begin']
            for previous in range(len(ports)):
                for b in range(4):
                    lines += [f'   if (rvw_mem_{previous}_mask[h][{b}] && {addr} == '
                              f'(rvw_mem_{previous}_address[h] + {width}\'d{b})) '
                              f'{expected} = rvw_mem_{previous}_data[h][{b*8} +: 8];']
            lines += ['  end', ' end',
                      f' if (!reset && {port["mask"]}[{lane}]) assume({value} == {expected});', 'end']
            # Reads in the same cycle see the same pre-write memory image.
            for other in reads[:n]:
                for b in range(4):
                    lines += [f'always @* if (!reset && {port["mask"]}[{lane}] && {other["mask"]}[{b}] && '
                              f'{addr} == ({other["address"]} + {width}\'d{b})) '
                              f'assume({value} == {other["data"]}[{8*b} +: 8]);']
    return '\n'.join(lines) + '\n'
