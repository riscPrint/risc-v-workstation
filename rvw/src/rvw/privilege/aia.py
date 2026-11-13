"""AIA 1.0 self-checking register campaigns, with explicit model-based oracles."""
from .controllers import Imsic, Aplic, AIA
from .programs import HEAD, TAIL


def check_value(register, expected):
    return f' {register}\n li t1, {expected}\n bne t0, t1, fail\n'


def indirect(selector, value):
    return f' li t0, {selector}\n csrw 0x350, t0\n li t0, {value}\n csrw 0x351, t0\n'


def write(address, value):
    return f' li t0, {address}\n li t1, {value}\n sw t1, 0(t0)\n fence iorw, iorw\n'


def programs(config):
    if config.get('spec_version') != AIA:
        raise ValueError('this model implements only AIA-1.0')
    rows=[]
    if config['kind']=='imsic':
        address=config['imsic']['msi_address']
        if address < 0 or address % 4096:raise ValueError('IMSIC file must be page aligned')
        for name, delivery, threshold, enable in [('priority',1,0,6),('threshold',1,2,6),
                ('delivery-off',0,0,6),('disabled',1,0,0)]:
            model=Imsic();model.delivery=bool(delivery);model.threshold=threshold;model.enabled={i for i in (1,2) if enable&(1<<i)}
            code=HEAD+indirect(0x70,0)+indirect(0x72,0)+indirect(0x80,0)+indirect(0xc0,enable)
            code+=indirect(0x72,threshold)+indirect(0x70,delivery)
            for identity in (2,1):
                code+=write(address,identity);model.inject(identity)
            if model.irq:
                code+=' li s0, 1000\n1: csrr t0, mip\n li t1, 0x800\n and t0, t0, t1\n bnez t0, 2f\n addi s0, s0, -1\n bnez s0, 1b\n j fail\n2:\n'
            else:
                code+=' csrr t0, mip\n li t1, 0x800\n and t0, t0, t1\n bnez t0, fail\n'
            expected=[]
            for _ in range(3):
                identity=model.claim();expected.append(identity)
                code+=check_value('csrrw t0, 0x35c, zero',(identity<<16)|identity)
            rows.append(dict(id='imsic-'+name,family='imsic',bins=['imsic.'+name],
                assembly=code+' j pass\n'+TAIL,
                reference_model=dict(kind='imsic',delivery=delivery,threshold=threshold,enable=enable,inject=[2,1],expected=expected)))
    else:
        base=config['aplic']['base'];context=config['aplic'].get('context',0)
        if base < 0 or base % 4096 or context < 0:raise ValueError('invalid APLIC domain map')
        for name,p1,p2,threshold,enable in [('tie',1,1,0,6),('priority',3,1,0,6),
                ('threshold',1,2,2,6),('disabled',1,2,0,0)]:
            model=Aplic();model.configure(1,1);model.configure(2,1)
            model.enabled={i for i in (1,2) if enable&(1<<i)};model.priority={1:p1,2:p2};model.threshold=threshold
            idc=base+0x4000+context*32
            code=HEAD+write(base,256)+write(base+4,1)+write(base+8,1)
            code+=write(base+0x1f00,6)+write(base+0x1d00,6)
            code+=write(base+0x3004,(context<<18)|p1)+write(base+0x3008,(context<<18)|p2)
            code+=write(idc,1)+write(idc+8,threshold)+write(base+0x1e00,enable)
            code+=write(base+0x1c00,6);model.pending={1,2}
            expected=[]
            for _ in range(3):
                source=model.claim();expected.append(source)
                value=(source<<16)|model.priority[source] if source else 0
                code+=f' li a0, {idc+0x1c}\n'+check_value('lw t0, 0(a0)',value)
            rows.append(dict(id='aplic-'+name,family='aplic',bins=['aplic.'+name],
                assembly=code+' j pass\n'+TAIL,
                reference_model=dict(kind='aplic',priority=[p1,p2],threshold=threshold,enable=enable,expected=expected)))
    for row in rows:row['spec']='https://docs.riscv.org/reference/aia/v1.0/index.html'
    return rows


def reference(scenario):
    plan=scenario['reference_model']
    if plan['kind']=='imsic':
        m=Imsic();m.delivery=bool(plan['delivery']);m.threshold=plan['threshold']
        m.enabled={i for i in (1,2) if plan['enable']&(1<<i)}
        for i in plan['inject']:m.inject(i)
    else:
        m=Aplic();m.configure(1,1);m.configure(2,1);m.pending={1,2}
        m.enabled={i for i in (1,2) if plan['enable']&(1<<i)}
        m.priority=dict(enumerate(plan['priority'],1));m.threshold=plan['threshold']
    actual=[m.claim() for _ in plan['expected']]
    return dict(id=scenario['id'],status='pass' if actual==plan['expected'] else 'fail',
                evidence='model-based',expected=plan['expected'],actual=actual)
