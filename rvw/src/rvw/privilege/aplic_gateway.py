"""AIA 1.0 level/edge-to-MSI gateway rules and generated MSI campaigns."""
from .controllers import Aplic, Imsic
from .aia import indirect,write,check_value
from .programs import HEAD,TAIL


class MsiAplic(Aplic):
    def __init__(self,sources=2):
        super().__init__(sources)
        self.domain_enabled=True

    def rectified(self,source,raw=None):
        mode=self.mode.get(source,0)
        if mode in (0,1):return False
        raw=self.level.get(source,False) if raw is None else bool(raw)
        return raw ^ (mode in (5,7))

    def set_level(self,source,level):
        if source in self.children:
            self.children[source].set_level(source,level);return
        old=self.rectified(source);self.level[source]=bool(level);new=self.rectified(source)
        mode=self.mode.get(source,0)
        if mode in (4,5,6,7) and new and not old:self.pending.add(source)
        if mode in (6,7) and not new:self.pending.discard(source)

    def software_pending(self,source,value):
        mode=self.mode.get(source,0)
        if source in self.children or mode==0:return
        if not value:self.pending.discard(source)
        elif mode not in (6,7) or self.rectified(source):self.pending.add(source)

    def msi(self):
        if not self.domain_enabled:return []
        messages=[]
        for source in sorted(self.pending & self.enabled):
            if self.mode.get(source,0) and source not in self.children and source in self.targets:
                messages.append(self.targets[source]);self.pending.discard(source)
        return messages


def programs(config):
    if config.get('spec_version')!='AIA-1.0':raise ValueError('APLIC MSI model implements AIA-1.0')
    base=config['aplic']['base'];msi=config['imsic']['msi_address']
    if base<0 or base%4096 or msi<0 or msi%4096:raise ValueError('invalid controller page map')
    rows=[]
    for mode in (4,5,6,7):
        inactive=mode in (5,7)
        levels=[inactive,not inactive,not inactive,inactive,not inactive]
        expected=[0,17,0,0,17]
        code=HEAD+indirect(0x70,0)+indirect(0x72,0)+indirect(0x80,0)+indirect(0xc0,1<<17)
        # One hart, one file. Project data supplies the destination page.
        code+=write(base,0)+write(base+4,0)+write(base+0x1f00,2)
        code+=write(base+0x1bc0,(msi>>12)&0xffffffff)+write(base+0x1bc4,(msi>>44)&0xfff)
        code+=write(base+0x3004,17)+write(base+0x1e00,2)
        events=[]
        for step,(level,identity) in enumerate(zip(levels,expected),1):
            events.append(dict(step=step,kind='aplic-level',controller_base=base,source=1,level=level))
            code+=f''' la t0, stimulus_step
 li t1, {step}
 sd t1, 0(t0)
 la t0, stimulus_ack
1: ld t1, 0(t0)
 li t2, {step}
 bne t1, t2, 1b
'''
            if step==1:
                code+=write(base+4,mode)+write(base+0x1e00,2)+write(base+0x3004,17)+write(base,0x104)
            if identity:
                code+=' li s0, 1000\n2: csrr t0, 0x35c\n bnez t0, 3f\n addi s0, s0, -1\n bnez s0, 2b\n j fail\n3:\n'
            code+=check_value('csrrw t0, 0x35c, zero',(identity<<16)|identity)
        code+=' j pass\n'+TAIL+'''.section .data
.balign 8
.globl stimulus_step, stimulus_ack
stimulus_step: .dword 0
stimulus_ack: .dword 0
'''
        rows.append(dict(id=f'aplic-msi-mode-{mode}',family='aplic',assembly=code,
            bins=[f'aplic.msi.mode.{mode}'],events=events,
            reference_model=dict(kind='aplic-msi',mode=mode,levels=levels,expected=expected),
            spec='https://github.com/riscv/riscv-aia/tree/f24dd483d50e6a1448116dcf88b8b08e0863512c'))
    return rows


def reference(scenario):
    p=scenario['reference_model'];a=MsiAplic();i=Imsic();i.enabled={17}
    actual=[]
    for step,level in enumerate(p['levels'],1):
        a.set_level(1,level)
        if step==1:a.configure(1,p['mode']);a.enabled={1};a.targets[1]=(0,17)
        for hart,identity in a.msi():i.inject(identity)
        actual.append(i.claim())
    return dict(id=scenario['id'],status='pass' if actual==p['expected'] else 'fail',
                evidence='model-based',actual=actual,expected=p['expected'])
