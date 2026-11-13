"""Small single-clock safety monitors used by automatic formal checks."""


def generate(prop, ports, signal, expr, clock, reset):
    kind = prop['kind']
    body = []
    if kind == 'dead_code':
        return body, f'!({expr(prop["target"])})'
    name = signal(prop['signal'])
    width = ports[name]['width']
    if kind == 'stuck_at':
        bit, value = prop['bit'], prop['value']
        if type(bit) is not int or not 0 <= bit < width or type(value) is not int or value not in (0, 1):
            raise ValueError('stuck-at needs an in-range bit and a zero/one value')
        return body, f"{name}[{bit}] == 1'b{value}"
    value = prop['value']
    if type(value) is not int or not 0 <= value < 2**width:
        raise ValueError('FSM state value does not fit signal')
    if kind == 'fsm_state':
        return body, f"!({name} == {width}'d{value})"
    previous = prop['source_value']
    if type(previous) is not int or not 0 <= previous < 2**width:
        raise ValueError('FSM source state does not fit signal')
    body += [f'reg [{width-1}:0] rvwa_previous;', 'reg rvwa_previous_valid = 0;',
             f'always @(posedge {clock}) begin',
             f' rvwa_previous_valid <= !{reset}; rvwa_previous <= {name}; end']
    return body, (f"!(rvwa_previous_valid && rvwa_previous == {width}'d{previous} "
                  f"&& {name} == {width}'d{value})")


def observation(kind, result):
    if result['status'] == 'fail':
        if kind in ('fsm_state', 'fsm_transition', 'dead_code', 'toggle', 'counter_wrap'):
            return 'reached'
        return 'not_constant' if kind == 'stuck_at' else 'violated'
    if result['status'] != 'pass':
        return 'inconclusive'
    unbounded = result['proof_kind'] == 'unbounded'
    if kind in ('fsm_state', 'fsm_transition', 'dead_code', 'toggle', 'counter_wrap'):
        return 'unreachable_conditional' if unbounded else 'not_observed_bounded'
    if kind == 'stuck_at':
        return 'constant_conditional' if unbounded else 'holds_bounded'
    return 'holds_conditional' if unbounded else 'holds_bounded'
