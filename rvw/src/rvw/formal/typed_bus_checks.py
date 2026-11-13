"""Typed multichannel safety checks. Transaction scoreboards remain separate."""
import re

CHANNELS = {'axi4': ('aw', 'w', 'b', 'ar', 'r'),
            'axi_lite4': ('aw', 'w', 'b', 'ar', 'r'),
            'tilelink': ('a', 'd')}


def render(kind, signals, name):
    """Return a module and connections for every enabled payload field."""
    channels = list(CHANNELS[kind])
    if kind == 'tilelink' and any(k.startswith('b.') for k in signals):
        channels = ['a', 'b', 'c', 'd', 'e']
    declarations, checks, ports = [], [], {}
    def field(key, required=True):
        if key not in signals:
            if required:
                raise ValueError('missing bus field '+key)
            return None
        row = signals[key]
        width = row[3]
        if not isinstance(width, int) or width < 1:
            raise ValueError('invalid field width '+key)
        net = re.sub(r'[^A-Za-z0-9_]', '_', key)
        if net in ports:
            raise ValueError('payload names collide after flattening')
        ports[net] = row[0]
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', row[0]):
            raise ValueError('invalid local signal name')
        declarations.append(f'input [{width-1}:0] {net}')
        return net
    for channel in channels:
        valid, ready = field(channel+'.valid'), field(channel+'.ready')
        if signals[channel+'.valid'][3] != 1 or signals[channel+'.ready'][3] != 1:
            raise ValueError('channel valid and ready must be one bit')
        keys = sorted(k for k in signals if k.startswith(channel+'.payload.'))
        if not keys:
            raise ValueError('missing complete payload for '+channel)
        nets = {k: field(k) for k in keys}
        payload = '{'+', '.join(nets.values())+'}'
        width = sum(signals[k][3] for k in keys)
        checks.append(f'''reg {channel}_stalled=0;
reg [{width-1}:0] {channel}_previous;
always @(posedge clk) begin
 if(reset) {channel}_stalled<=0;
 else begin
  if({channel}_stalled) begin assert({valid}); assert({payload} == {channel}_previous); end
  {channel}_stalled <= {valid} && !{ready};
  {channel}_previous <= {payload};
 end
end''')
        if kind.startswith('axi') and channel in ('aw', 'ar'):
            addr = nets.get(channel+'.payload.addr')
            if not addr:
                raise ValueError('missing address field')
            if kind == 'axi4':
                burst = nets.get(channel+'.payload.burst')
                length = nets.get(channel+'.payload.len')
                size = nets.get(channel+'.payload.size')
                if not all((burst, length, size)):
                    raise ValueError('full AXI4 burst fields are required')
                # WRAP is aligned to the beat, not necessarily to its wrap span.
                checks.append(f'''always @(posedge clk) if(!reset && {valid}) begin
 assert({burst} != 3);
 if({burst} == 0) assert({length} < 16);
 if({burst} == 2) begin
  assert({length} == 1 || {length} == 3 || {length} == 7 || {length} == 15);
  assert(({addr} & ((64'd1 << {size})-1)) == 0);
 end
end''')
        if kind == 'axi_lite4' and channel in ('b', 'r'):
            resp = nets.get(channel+'.payload.resp')
            if not resp:
                raise ValueError('missing AXI-Lite response')
            checks.append(f'always @(posedge clk) if(!reset && {valid}) assert({resp} != 1);')
        if kind == 'tilelink' and channel != 'e':
            opcode = nets.get(channel+'.payload.opcode')
            if not opcode:
                raise ValueError('missing TileLink opcode')
            allowed = {'a': range(8), 'b': range(8), 'c': (0,1,2,4,5,6,7), 'd': (0,1,2,4,5,6)}[channel]
            checks.append(f'always @(posedge clk) if(!reset && {valid}) assert('+
                          ' || '.join(f'{opcode} == {n}' for n in allowed)+');')
    return ('module '+name+'(input clk, reset, '+', '.join(declarations)+');\n'+
            '\n'.join(checks)+'\nendmodule\n', ports)
