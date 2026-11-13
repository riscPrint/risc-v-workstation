"""Safety and observation monitors for structurally discovered roles."""


def generate(prop, ports, signal, clock, reset):
    kind=prop['kind']
    if kind=='counter_wrap':
        name=signal(prop['signal']); width=ports[name]['width']
        return [f'reg [{width-1}:0] rvwa_previous;', 'reg rvwa_seen=0;',
                f'always @(posedge {clock}) begin rvwa_seen<=!{reset}; rvwa_previous<={name}; end'], \
               f'!(rvwa_seen && rvwa_previous=={width}\'d{(1<<width)-1} && {name}==0)'
    def channel(c):
        valid,ready,data=(signal(c[k]) for k in ('valid','ready','payload'))
        if ports[valid]['width']!=1 or ports[ready]['width']!=1:
            raise ValueError('channel controls need one bit')
        return f'({valid} && {ready})',data
    inputs=[channel(c) for c in prop['inputs']]
    pop,output=channel(prop['output']); width=ports[output]['width']
    if any(ports[d]['width']!=width for _,d in inputs):
        raise ValueError('channel payload widths differ')
    if kind=='arbiter_transfer':
        n=len(inputs)
        if n<2: raise ValueError('arbiter needs at least two inputs')
        events=', '.join(e for e,_ in inputs)
        body=[f'wire [{n-1}:0] rvwa_accept = {{{events}}};']
        conditions=[f'((rvwa_accept & (rvwa_accept-1))==0)',f'((|rvwa_accept)=={pop})']
        conditions += [f'(!{event} || ({output}=={data}))' for event,data in inputs]
        return body,' && '.join(conditions)
    if kind!='fifo_stream' or len(inputs)!=1:
        raise ValueError('unsupported discovered role monitor')
    push,data=inputs[0]; capacity=prop['capacity']
    if type(capacity) is not int or not 1<=capacity<=1024:
        raise ValueError('FIFO depth must be 1..1024')
    clear=signal(prop['clear']) if prop.get('clear') else "1'b0"
    if prop.get('clear') and ports[clear]['width']!=1:
        raise ValueError('FIFO clear needs one bit')
    body=[f'reg [{width-1}:0] rvwa_queue [0:{capacity-1}];',
        'integer rvwa_count=0, rvwa_read=0, rvwa_write=0;',
        f'always @(posedge {clock}) begin',
        f' if ({reset} || {clear}) begin rvwa_count<=0; rvwa_read<=0; rvwa_write<=0; end else begin',
        f' if ({pop} && rvwa_count>0) begin assert({output}==rvwa_queue[rvwa_read]); rvwa_read<=rvwa_read=={capacity-1}?0:rvwa_read+1; end',
        f' if ({pop} && rvwa_count==0 && {push}) assert({output}=={data});',
        f' if ({push} && !(rvwa_count==0 && {pop})) begin rvwa_queue[rvwa_write]<={data}; rvwa_write<=rvwa_write=={capacity-1}?0:rvwa_write+1; end',
        f' if ({push} && !{pop}) rvwa_count<=rvwa_count+1;',
        f' if ({pop} && !{push}) rvwa_count<=rvwa_count-1;', ' end end']
    return body,f'{clear} || ((!{pop} || rvwa_count>0 || {push}) && (!{push} || {pop} || rvwa_count<{capacity}))'
