"""AIA direct-domain delegation, revocation and redelegation transactions."""
from .controllers import Aplic
from .aia import revision,write,poll_value
from .programs import HEAD,TAIL

VERSION='AIA-1.0'


def address(plan,domain,register):
    base=plan[domain+'_base'];source=plan['source']
    if register=='cfg':return base+4*source
    if register=='target':return base+0x3000+4*source
    if register=='claim':return base+0x401c+32*plan[domain+'_context']
    return base+dict(ip=0x1c00,clear_ip=0x1d00,ie=0x1e00,clear_ie=0x1f00)[register]+4*(source//32)


class Domains:
    """One configured source and two domains; other sources stay inactive."""
    def __init__(self,plan):
        self.plan=plan;self.source=plan['source'];self.delegated=False
        self.root=Aplic(plan['implemented_sources']);self.child=Aplic(plan['implemented_sources'])

    def owns(self,domain):return self.delegated if domain=='child' else not self.delegated

    def execute(self,operation):
        source=self.source;kind=operation['op']
        if kind=='route':
            self.delegated=bool(operation['value'])
            self.root.children.pop(source,None)
            self.root.configure(source,0 if self.delegated else 1)
            self.child.configure(source,0)
            if self.delegated:self.root.children[source]=self.child
            return None
        domain=operation['domain'];register=operation['register'];m=getattr(self,domain)
        if kind=='write':
            if not self.owns(domain):return None
            value=operation['value']
            if register=='cfg':m.configure(source,value)
            elif m.mode.get(source,0):
                if register=='target':m.priority[source]=value&255
                elif register=='ie':m.enabled.add(source)
                elif register=='clear_ie':m.enabled.discard(source)
                elif register=='ip':m.pending.add(source)  # Detached source.
                elif register=='clear_ip':m.pending.discard(source)
                else:raise ValueError('unsupported delegation register')
            return None
        if kind!='read':raise ValueError('unsupported delegation operation')
        if register=='cfg' and domain=='root' and self.delegated:return 0x400|self.plan['child_index']
        if not self.owns(domain):return 0
        if register=='cfg':return m.mode.get(source,0)
        if not m.mode.get(source,0):return 0
        if register=='ip':return (1<<(source%32)) if source in m.pending else 0
        if register=='ie':return (1<<(source%32)) if source in m.enabled else 0
        if register=='claim':
            claimed=m.claim()
            return (claimed<<16)|m.priority.get(claimed,1) if claimed else 0
        raise ValueError('unsupported delegation read')


def programs(config):
    if config.get('spec_version')!=VERSION:raise ValueError('APLIC delegation requires AIA-1.0')
    selected=revision(config);options=config['aplic'];count=options['implemented_sources']
    if options.get('direct_delivery') is not True:raise ValueError('declare direct delivery support')
    if type(count) is not int or not 1<=count<=1023:raise ValueError('implemented_sources must be 1..1023')
    sources=options['source_ids']
    if not sources or len(set(sources))!=len(sources) or any(type(s) is not int or not 1<=s<=count for s in sources):
        raise ValueError('select distinct implemented source_ids')
    for key in ('parent_base','child_base'):
        if type(options[key]) is not int or options[key]<0 or options[key]%4096:raise ValueError('domain bases must be page aligned')
    if options['parent_base']==options['child_base']:raise ValueError('domains need distinct control maps')
    if type(options['child_index']) is not int or not 0<=options['child_index']<1024:raise ValueError('invalid child index')
    rows=[]
    for source in sources:
        plan=dict(kind='aplic-delegation',source=source,implemented_sources=count,root_base=options['parent_base'],
            child_base=options['child_base'],child_index=options['child_index'],root_context=options.get('parent_context',0),child_context=options.get('child_context',0),operations=[],expected=[])
        if any(type(plan[d+'_context']) is not int or plan[d+'_context']<0 for d in ('root','child')):raise ValueError('invalid context')
        code=HEAD;mask=1<<(source%32);identity=(source<<16)|1
        for i in range(1,count+1):code+=write(plan['root_base']+4*i,0)
        for domain in ('root','child'):
            base=plan[domain+'_base'];idc=base+0x4000+32*plan[domain+'_context']
            code+=write(base,0x100)+write(idc,1)+write(idc+8,0)
        def route(delegated):
            nonlocal code
            plan['operations'].append(dict(op='route',value=delegated))
            code+=write(address(plan,'root','cfg'),(0x400|plan['child_index']) if delegated else 1)
        def put(domain,register,value):
            nonlocal code
            plan['operations'].append(dict(op='write',domain=domain,register=register,value=value))
            code+=write(address(plan,domain,register),value)
        def read(domain,register,value):
            nonlocal code
            index=len(plan['expected']);plan['expected'].append(value)
            plan['operations'].append(dict(op='read',domain=domain,register=register))
            bits=mask if register in ('ip','ie') else 0xffffffff
            code+=f''' li a0, {address(plan,domain,register)}
delegation_read_{index}:
 lw t0, 0(a0)
 li t1, {bits}
 and t0, t0, t1
 li t1, {value}
 bne t0, t1, fail
'''
        def inject(domain,phase):
            nonlocal code
            put(domain,'clear_ie',mask);put(domain,'clear_ip',mask)
            put(domain,'target',(plan[domain+'_context']<<18)|1)
            put(domain,'ie',mask);put(domain,'ip',mask)
            code+=f' li a0, {address(plan,domain,"ip")}\n'+poll_value('lw t0, 0(a0)',mask,mask,f'delegation_pending_{phase}',options.get('poll_iterations',1000))
            read(domain,'ip',mask)
        # The parent cannot set IP/EIE for a delegated source.
        route(True);read('root','cfg',0x400|plan['child_index']);read('child','cfg',0)
        put('child','cfg',1);put('root','ie',mask);put('root','ip',mask)
        read('root','ie',0);read('root','ip',0)
        inject('child',1);read('root','claim',0);read('child','claim',identity);read('child','claim',0)
        # Revocation makes the child's per-source state read-only zero.
        route(False);read('root','cfg',1);read('child','cfg',0)
        put('child','ie',mask);put('child','ip',mask);read('child','ie',0);read('child','ip',0)
        inject('root',2);read('child','claim',0);read('root','claim',identity);read('root','claim',0)
        # A newly delegated child must start with sourcecfg zero.
        route(True);read('root','cfg',0x400|plan['child_index']);read('child','cfg',0)
        read('root','ie',0);read('root','ip',0);put('child','cfg',1)
        inject('child',3);read('root','claim',0);read('child','claim',identity);read('child','claim',0)
        rows.append(dict(id=f'aplic-delegation-{source}',family='aplic',assembly=code+' j pass\n'+TAIL,
            bins=[f'aplic.delegation.{source}',f'aplic.revocation.{source}',f'aplic.redelegation.{source}'],
            reference_model=plan,reference_mode='model-observations',model_bindings=observation_bindings(plan),
            spec_version=VERSION,spec_revision=selected,spec='https://github.com/riscv/riscv-aia/tree/'+selected))
    return rows


def reference(scenario):
    revision(scenario);p=scenario['reference_model'];model=Domains(p);actual=[]
    for operation in p['operations']:
        value=model.execute(operation)
        if operation['op']=='read':actual.append(value)
    return dict(id=scenario['id'],status='pass' if actual==p['expected'] else 'fail',actual=actual,expected=p['expected'],evidence='model-based',
                scope='one Detached source through two direct-delivery domains; no DUT execution')


def observation_bindings(plan):
    reads=[op for op in plan['operations'] if op['op']=='read'];mask=1<<(plan['source']%32)
    return [dict(symbol=f'delegation_read_{i}',kind='load',address=hex(address(plan,op['domain'],op['register'])),width=4,
                 mask=hex(mask if op['register'] in ('ip','ie') else 0xffffffff),expected=[hex(value)])
            for i,(op,value) in enumerate(zip(reads,plan['expected']))]
