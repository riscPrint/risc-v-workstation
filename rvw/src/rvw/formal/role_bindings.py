"""Bind standard component roles using typed channels and memory structure."""


def bind(role, channels, memories, ports, cid):
    inputs=[c for c in channels if ports[c['valid']]['direction']=='input' and ports[c['ready']]['direction']=='output']
    outputs=[c for c in channels if ports[c['valid']]['direction']=='output' and ports[c['ready']]['direction']=='input']
    if len(outputs)!=1 or not inputs:
        return None
    prop=dict(id=f'role_{role}_{cid}',inputs=inputs,output=outputs[0])
    if role=='fifo' and len(inputs)==1 and len(memories)==1:
        _,depth,width=memories[0]
        if type(depth) is not int or not 1<=depth<=1024 or ports[inputs[0]['payload']]['width']!=width:
            return None
        prop.update(kind='fifo_stream',capacity=depth)
        # StreamFifo's optional flush input is part of its standard interface.
        if 'io_flush' in ports: prop['clear']='io_flush'
        return prop
    if role=='arbiter' and len(inputs)>1:
        prop['kind']='arbiter_transfer'
        return prop
    return None
