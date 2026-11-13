"""AIA 1.0 self-checking register campaigns, with explicit model-based oracles."""
from .controllers import Imsic, Aplic, AIA
from .programs import HEAD, TAIL

VERSION=AIA
REVISION='20318d1b03f0ac8253458b82f8244d0d0db074e9'
REVISIONS=(REVISION,'f24dd483d50e6a1448116dcf88b8b08e0863512c')


def priority_bits(options):
    bits=options.get('priority_bits',8)
    if type(bits) is not int or not 1<=bits<=8:raise ValueError('priority_bits must be 1..8')
    return bits


def revision(config):
    selected=config.get('spec_revision',REVISION)
    if selected not in REVISIONS:raise ValueError('unsupported AIA document revision')
    return selected


def check_value(register, expected, label=None):
    return (label+':\n' if label else '')+f' {register}\n li t1, {expected}\n bne t0, t1, fail\n'


def poll_value(operation,mask,value,label,iterations):
    if type(iterations) is not int or iterations<1:raise ValueError('poll_iterations must be positive')
    return f''' li s0, {iterations}
{label}_wait:
 {operation}
 li t1, {mask}
 and t0, t0, t1
 li t1, {value}
 beq t0, t1, {label}_ready
 addi s0, s0, -1
 bnez s0, {label}_wait
 j fail
{label}_ready:
{label}:
 {operation}
'''


def indirect(selector, value, *, select=0x350, register=0x351):
    return f' li t0, {selector}\n csrw {select:#x}, t0\n li t0, {value}\n csrw {register:#x}, t0\n'


def write(address, value):
    return f' li t0, {address}\n li t1, {value}\n sw t1, 0(t0)\n fence iorw, iorw\n'


def programs(config):
    if config.get('spec_version') != AIA:
        raise ValueError('this model implements only AIA-1.0')
    selected_revision=revision(config);rows=[]
    if config['kind']=='imsic':
        data=config['imsic'];address=data['msi_address'];file=data.get('file','M')
        if address < 0 or address % 4096:raise ValueError('IMSIC file must be page aligned')
        if file not in ('M','S','VS'):raise ValueError('IMSIC file must be M, S or VS')
        guest=data.get('guest_index',1)
        if file=='VS' and ('h' not in config.get('isa','').split('_')[0][4:] or type(guest) is not int or not 1<=guest<=63):
            raise ValueError('VS interrupt files require H and guest index 1..63')
        select,register,top,irq={'M':(0x350,0x351,0x35c,11),'S':(0x150,0x151,0x15c,9),'VS':(0x250,0x251,0x25c,10)}[file]
        peer_select,peer_register,peer_top=(0x150,0x151,0x15c) if file=='M' else (0x350,0x351,0x35c)
        def put(selector,value):return indirect(selector,value,select=select,register=register)
        def peer(selector,value):return indirect(selector,value,select=peer_select,register=peer_register)
        identities=data.get('identities',63)
        Imsic(identities)
        peer_identities=data.get('peer_identities',identities);Imsic(peer_identities)
        polls=data.get('poll_iterations',1000)
        for name, delivery, threshold, enable in [('priority',1,0,6),('threshold',1,2,6),
                ('delivery-off',0,0,6),('disabled',1,0,0)]:
            model=Imsic(identities);model.delivery=bool(delivery);model.threshold=threshold;model.enabled={i for i in (1,2) if enable&(1<<i)}
            code=HEAD
            if file=='VS':code+=f' li t0, 0x3f000\n csrc hstatus, t0\n li t0, {guest<<12}\n csrs hstatus, t0\n'
            code+=put(0x70,0)+peer(0x70,0)+peer(0x72,0)
            for word in range((identities+1)//64):
                code+=put(0x80+2*word,0)+put(0xc0+2*word,0)
            # The untouched peer checks file isolation at the core interface.
            for word in range((peer_identities+1)//64):
                code+=peer(0x80+2*word,0)+peer(0xc0+2*word,0)
            code+=peer(0xc0,6)
            code+=put(0xc0,enable)+put(0x72,threshold)+put(0x70,delivery)
            for identity in (2,1):
                code+=write(address,identity);model.inject(identity)
            # MSI writes may take effect later than the stores. Wait for both
            # pending identities before comparing priority, even with delivery off.
            code+=f' li t0, 0x80\n csrw {select:#x}, t0\n'
            code+=poll_value(f'csrr t0, {register:#x}',6,6,'imsic_pending_read',polls)
            expected_irq=bool(model.irq)
            code+=poll_value('csrr t0, mip',1<<irq,(1<<irq) if expected_irq else 0,'imsic_irq_read',polls)
            code+=check_value(f'csrr t0, {peer_top:#x}',0,'imsic_peer_read')
            expected=[]
            for index in range(3):
                identity=model.claim();expected.append(identity)
                code+=check_value(f'csrrw t0, {top:#x}, zero',(identity<<16)|identity,f'imsic_claim_{index}')
            suffix='' if file=='M' else '-s' if file=='S' else f'-vs{guest}'
            rows.append(dict(id='imsic-'+name+suffix,family='imsic',bins=[f'imsic.{file}.{name}'],
                assembly=code+' j pass\n'+TAIL,
                reference_model=dict(kind='imsic',file=file,identities=identities,peer_identities=peer_identities,delivery=delivery,threshold=threshold,enable=enable,inject=[2,1],irq=expected_irq,expected=expected)))
    else:
        base=config['aplic']['base'];context=config['aplic'].get('context',0)
        bits=priority_bits(config['aplic']);maximum=(1<<bits)-1
        if base < 0 or base % 4096 or context < 0:raise ValueError('invalid APLIC domain map')
        for name,p1,p2,threshold,enable in [('tie',1,1,0,6),('priority',3,1,0,6),
                ('threshold',1,2,2,6),('disabled',1,2,0,0)]:
            p1=(p1&maximum) or 1;p2=(p2&maximum) or 1;threshold=min(threshold,maximum)
            model=Aplic();model.configure(1,1);model.configure(2,1)
            model.enabled={i for i in (1,2) if enable&(1<<i)};model.priority={1:p1,2:p2};model.threshold=threshold
            idc=base+0x4000+context*32
            code=HEAD+write(base,256)+write(base+4,1)+write(base+8,1)
            code+=write(base+0x1f00,6)+write(base+0x1d00,6)
            code+=write(base+0x3004,(context<<18)|p1)+write(base+0x3008,(context<<18)|p2)
            code+=write(idc,1)+write(idc+8,threshold)+write(base+0x1e00,enable)
            code+=write(base+0x1c00,6);model.pending={1,2}
            code+=f' li a0, {base+0x1c00}\n'+poll_value('lw t0, 0(a0)',6,6,'aplic_pending_read',config['aplic'].get('poll_iterations',1000))
            expected=[]
            for index in range(3):
                source=model.claim();expected.append(source)
                value=(source<<16)|model.priority[source] if source else 0
                code+=f' li a0, {idc+0x1c}\n'+check_value('lw t0, 0(a0)',value,f'aplic_claim_{index}')
            rows.append(dict(id='aplic-'+name,family='aplic',bins=['aplic.'+name,f'aplic.priority-bits.{bits}'],
                assembly=code+' j pass\n'+TAIL,
                reference_model=dict(kind='aplic',priority_bits=bits,priority=[p1,p2],threshold=threshold,enable=enable,pending_address=base+0x1c00,claim_address=idc+0x1c,expected=expected)))
    for row in rows:
        row.update(spec='https://github.com/riscv/riscv-aia/tree/'+selected_revision,spec_version=VERSION,spec_revision=selected_revision,
                   reference_mode='model-observations',model_bindings=observation_bindings(row['reference_model']))
    return rows


def reference(scenario):
    revision(scenario)
    plan=scenario['reference_model']
    if plan['kind']=='imsic':
        m=Imsic(plan.get('identities',63));m.delivery=bool(plan['delivery']);m.threshold=plan['threshold']
        m.enabled={i for i in (1,2) if plan['enable']&(1<<i)}
        for i in plan['inject']:m.inject(i)
    else:
        maximum=(1<<priority_bits(plan))-1
        if any(not 1<=p<=maximum for p in plan['priority']) or not 0<=plan['threshold']<=maximum:
            raise ValueError('priority plan exceeds IPRIOLEN')
        m=Aplic();m.configure(1,1);m.configure(2,1);m.pending={1,2}
        m.enabled={i for i in (1,2) if plan['enable']&(1<<i)}
        m.priority=dict(enumerate(plan['priority'],1));m.threshold=plan['threshold']
    irq_matches=plan.get('irq',bool(m.irq))==bool(m.irq)
    actual=[m.claim() for _ in plan['expected']]
    return dict(id=scenario['id'],status='pass' if actual==plan['expected'] and irq_matches else 'fail',
                evidence='model-based',expected=plan['expected'],actual=actual)


def observation_bindings(plan):
    if plan['kind']=='imsic':
        register,top,irq={'M':(0x351,0x35c,11),'S':(0x151,0x15c,9),'VS':(0x251,0x25c,10)}[plan['file']]
        peer=0x15c if plan['file']=='M' else 0x35c
        result=[dict(symbol='imsic_pending_read',kind='csr',csr=hex(register),mask='0x6',expected=['0x6']),
                dict(symbol='imsic_irq_read',kind='csr',csr='0x344',mask=hex(1<<irq),expected=[hex((1<<irq) if plan['irq'] else 0)]),
                dict(symbol='imsic_peer_read',kind='csr',csr=hex(peer),expected=['0x0'])]
        result.extend(dict(symbol=f'imsic_claim_{i}',kind='csr-exchange',csr=hex(top),expected=[hex((identity<<16)|identity)]) for i,identity in enumerate(plan['expected']))
        return result
    priority=dict(enumerate(plan['priority'],1))
    return [dict(symbol='aplic_pending_read',kind='load',address=hex(plan['pending_address']),width=4,mask='0x6',expected=['0x6'])]+[
        dict(symbol=f'aplic_claim_{i}',kind='load',address=hex(plan['claim_address']),width=4,expected=[hex((source<<16)|priority[source] if source else 0)])
        for i,source in enumerate(plan['expected'])]
