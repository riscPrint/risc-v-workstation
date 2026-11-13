"""Generate consumer inputs from the same composition that wires the RTL."""
from .model import dumps


def files(model, spec, composition):
    checks = {
        'protocol': {'composition': composition, 'classpath_file': 'runtime-classpath.txt'},
        'registers': {'capture': 'apb.jsonl', 'write_read': [r['name']+'.'+v['name']
            for r in model['regions'] for v in r['registers'] if v['access']=='rw']},
        'vip': {'composition': composition, 'classpath_file': 'runtime-classpath.txt'},
        'uvm': {'composition': composition, 'classpath_file': 'runtime-classpath.txt'},
        'decode': {'classpath_file': 'runtime-classpath.txt'},
        'connectivity': {'database': 'soc.db', 'manifest': 'connections.json', 'cone_cut': True},
        'cdc_rdc': {'database': 'soc.db'},
    }
    rows = [dict(id='core_reset',kind='required',source='reset',destination='core.reset')]
    for region in model['regions']:
        name = region['name']
        binder = spec['devices'][name]
        if binder['type']=='host':
            continue
        domain = binder.get('domain')
        for pin in ('clk','reset'):
            rows.append(dict(id=name+'_'+pin,kind='required',
                             source=domain+'_'+pin if domain else pin,
                             destination=name+'.'+pin))
    # Direct one-source interrupt transfers have equal scalar widths.
    # Aggregated and synchronized interrupts need temporal project contracts.
    for cause in sorted({i['cause'] for i in model['interrupts']}):
        sources = [i for i in model['interrupts'] if i['cause']==cause]
        if len(sources)==1:
            irq = sources[0]
            binder = spec['devices'][irq['region']]
            if not binder.get('domain'):
                pin = binder.get('irq',{}).get(irq['name'],'irq')
                rows.append(dict(id='interrupt_'+str(cause),kind='required',
                    source=irq['region']+'.io_'+pin,destination='interrupt_'+str(cause)))
    registers = [dict(region=r['name'], **v) for r in model['regions'] for v in r['registers']]
    return {'verify.json': dumps(dict(schema='rvw.soc-verify/1',checks=checks)),
            'connections.json': dumps(dict(connection=rows)),
            'register-checks.json': dumps(dict(schema='rvw.soc-register-checks/1',registers=registers,
                scope='Map declarations; native APB capture is required.'))}
