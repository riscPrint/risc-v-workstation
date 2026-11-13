"""Digital seed-CSR protocol checks. No physical entropy claim."""

def generate(prop, ports, signal, clock, reset):
    names={key:signal(prop[key]) for key in ('seed','access','write','allowed','illegal','refill','fatal')}
    for key,name in names.items():
        port=ports[name]
        direction='output' if key in ('seed','illegal') else 'input'
        widths=(32,64) if key=='seed' else (1,)
        if port['direction']!=direction or port['width'] not in widths:
            raise ValueError('seed needs 32/64 output; illegal needs scalar output; controls need scalar inputs')
    seed,access,write,allowed,illegal,refill,fatal=(names[k] for k in ('seed','access','write','allowed','illegal','refill','fatal'))
    state=f'{seed}[31:30]';poll=f'({access} && {write} && {allowed} && !{illegal})'
    extra=['reg rvwa_entropy_valid = 0;', 'reg [1:0] rvwa_entropy_state;',
           'reg rvwa_entropy_poll,rvwa_entropy_refill,rvwa_entropy_fatal;',
           f'always @(posedge {clock}) begin',
           f'if ({reset}) rvwa_entropy_valid <= 0;',
           'else begin rvwa_entropy_valid <= 1;',
           f'rvwa_entropy_state <= {state}; rvwa_entropy_poll <= {poll};',
           f'rvwa_entropy_refill <= {refill}; rvwa_entropy_fatal <= {fatal}; end end']
    conditions=[f'({state} == 2 || {seed}[15:0] == 0)',
                f'(!{access} || ({illegal} == !({write} && {allowed})))',
                f'(!rvwa_entropy_valid || (!rvwa_entropy_fatal && rvwa_entropy_state != 3) || {state} == 3)',
                f'(!rvwa_entropy_valid || rvwa_entropy_state != 0 || rvwa_entropy_poll || {state} == 0 || {state} == 3)',
                f'(!rvwa_entropy_valid || rvwa_entropy_state != 2 || !rvwa_entropy_poll || rvwa_entropy_refill || {state} != 2)']
    if ports[seed]['width']==64:conditions.append(f'({seed}[63:32] == 0)')
    return extra,' && '.join(conditions)
