"""Explicit finite-service environments for in-order command/response buses.

This adds service assumptions to the ready/valid handshake used by the protocol
monitors. It does not assume that a core produces valid requests or retires.
"""


def render(plan, locals):
    lines = []
    records = []
    for index, bus in enumerate(plan.get('bus_environment', [])):
        if bus.get('protocol') != 'stream-response':
            raise ValueError('unsupported fairness protocol; expected stream-response')
        bound = bus['service_bound']
        capacity = bus.get('max_pending', 8)
        if type(bound) is not int or not 1 <= bound <= 64:
            raise ValueError('service_bound must be 1..64')
        if type(capacity) is not int or not 1 <= capacity <= 64:
            raise ValueError('max_pending must be 1..64')
        def signal(key, direction):
            port = bus[key]
            if plan.get(direction, {}).get(port) != 1:
                raise ValueError(f'{key} must bind a one-bit {direction} port')
            return locals[port]
        valid = signal('valid', 'outputs')
        ready = signal('ready', 'inputs')
        response = signal('response', 'inputs')
        read = signal('write', 'outputs') if 'write' in bus else "1'b0"
        p = f'env_{index}'
        lines += [f'''// stream-response: response service bound {bound}, capacity {capacity}.
integer {p}_pending = 0;
integer {p}_stall = 0;
integer {p}_age = 0;
wire {p}_accept = {valid} && {ready} && !{read};
always @(posedge clock) begin
 if (reset) begin
  {p}_pending <= 0; {p}_stall <= 0; {p}_age <= 0;
 end else begin
  // Environment controls ready and response. Requests stay unconstrained.
  if ({p}_stall == {bound-1}) assume({ready});
  if ({valid} && !{ready}) {p}_stall <= {p}_stall + 1;
  else {p}_stall <= 0;
  assume(!{response} || {p}_pending > 0);
  if ({p}_pending > 0 && {p}_age == {bound-1}) assume({response});
  if ({p}_pending > 0 && !{response}) {p}_age <= {p}_age + 1;
  else {p}_age <= 0;
  {p}_pending <= {p}_pending + {p}_accept - {response};
  // Capacity is checked, never assumed about DUT requests.
  assert({p}_pending >= 0 && {p}_pending <= {capacity});
 end
end''']
        records.append(dict(bus, response_policy='in-order, no unsolicited or same-cycle response',
                            fairness='one response per service_bound cycles while pending'))
    for port, value in plan.get('environment_constants', {}).items():
        if port not in plan.get('inputs', {}) or type(value) is not int or not 0 <= value < 2**plan['inputs'][port]:
            raise ValueError('environment constant must fit a declared input')
        lines.append(f'always @* assume({locals[port]} == {plan["inputs"][port]}\'d{value});')
    return lines, records
