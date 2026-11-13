"""AIA IPRIOLEN target conversion and legal threshold boundary probes."""
from .aia import revision,priority_bits,write,poll_value
from .controllers import Aplic
from .programs import HEAD,TAIL

VERSION='AIA-1.0'


def location(plan,kind):
    base=plan['base'];source=plan['source'];context=plan['context']
    return dict(target=base+0x3000+4*source,threshold=base+0x4008+32*context,claim=base+0x401c+32*context)[kind]


def programs(config):
    if config.get('spec_version')!=VERSION or not config['isa'].startswith('rv64'):
        raise ValueError('APLIC priority requires RV64 AIA-1.0')
    selected=revision(config);o=config['aplic'];bits=priority_bits(o);maximum=(1<<bits)-1
    source=o['source_id'];count=o['implemented_sources'];base=o['base'];context=o.get('context',0)
    if type(count) is not int or type(source) is not int or not 1<=source<=count<=1023:raise ValueError('select an implemented source')
    if type(base) is not int or base<0 or base%4096 or type(context) is not int or context<0:raise ValueError('invalid domain map')
    plan=dict(kind='aplic-priority',base=base,source=source,context=context,implemented_sources=count,priority_bits=bits,actions=[],expected=[])
    mask=1<<(source%32);word=4*(source//32);idc=base+0x4000+32*context
    code=HEAD
    for s in range(1,count+1):code+=write(base+4*s,0)
    # Delivery is disabled. TOPI/claim values do not depend on delivery enables.
    code+=write(base,0)+write(idc,0)+write(base+4*source,1)+write(base+0x1e00+word,mask)
    def put(kind,value):
        nonlocal code
        plan['actions'].append(dict(op=kind,value=value))
        code+=write(location(plan,'target' if kind=='priority' else 'threshold'),((context<<18)|value) if kind=='priority' else value)
    def get(kind,value):
        nonlocal code
        index=len(plan['expected']);plan['expected'].append(value);plan['actions'].append(dict(op='read',register=kind))
        code+=f''' li a0, {location(plan,kind)}
priority_read_{index}:
 lw t0, 0(a0)
 li t1, {value}
 bne t0, t1, fail
'''
    def pending():
        nonlocal code
        stage=len(plan['actions']);plan['actions'].append(dict(op='inject'))
        code+=write(base+0x1c00+word,mask)+f' li a0, {base+0x1c00+word}\n'
        code+=poll_value('lw t0, 0(a0)',mask,mask,f'priority_pending_{stage}',o.get('poll_iterations',1000))
    put('threshold',0)
    raw_values=list(dict.fromkeys([0,1,2,3,maximum,maximum+1,0x80,0xff]))
    for raw in raw_values:
        value=(raw%(1<<bits)) or 1
        put('priority',raw);get('target',(context<<18)|value)
        pending();get('claim',(source<<16)|value);get('claim',0)
    for value in sorted({1,maximum}):
        put('priority',value);get('target',(context<<18)|value)
        put('threshold',value);get('threshold',value)
        pending();get('claim',0)
        put('threshold',0);get('threshold',0);get('claim',(source<<16)|value);get('claim',0)
    return [dict(id=f'aplic-priority-{bits}-{source}',family='aplic',assembly=code+' j pass\n'+TAIL,
        bins=[f'aplic.ipriolen.{bits}',f'aplic.priority-zero.{bits}',f'aplic.threshold-boundary.{bits}'],
        spec_version=VERSION,spec_revision=selected,spec='https://github.com/riscv/riscv-aia/tree/'+selected,
        reference_mode='model-observations',reference_model=plan,model_bindings=observation_bindings(plan))]


def reference(scenario):
    revision(scenario);p=scenario['reference_model'];bits=priority_bits(p);source=p['source'];m=Aplic(p['implemented_sources'])
    m.configure(source,1);m.enabled={source};m.delivery=False;actual=[]
    for action in p['actions']:
        operation=action['op']
        if operation=='priority':m.priority[source]=(action['value']&((1<<bits)-1)) or 1
        elif operation=='threshold':
            if not 0<=action['value']<1<<bits:raise ValueError('unmodeled WLRL threshold write')
            m.threshold=action['value']
        elif operation=='inject':m.pending.add(source)
        elif operation=='read':
            register=action['register']
            if register=='target':actual.append((p['context']<<18)|m.priority[source])
            elif register=='threshold':actual.append(m.threshold)
            else:
                claimed=m.claim();actual.append((claimed<<16)|m.priority[claimed] if claimed else 0)
        else:raise ValueError('unsupported priority action')
    return dict(id=scenario['id'],status='pass' if actual==p['expected'] else 'fail',evidence='model-based',actual=actual,expected=p['expected'],
                scope='IPRIOLEN target conversion and legal direct threshold boundaries; no DUT or IRQ delivery')


def observation_bindings(plan):
    reads=[a for a in plan['actions'] if a['op']=='read']
    return [dict(symbol=f'priority_read_{i}',kind='load',address=hex(location(plan,a['register'])),width=4,expected=[hex(value)])
            for i,(a,value) in enumerate(zip(reads,plan['expected']))]
