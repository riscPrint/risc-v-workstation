"""Native Spike ISA plus a bounded APLIC direct/Detached register model."""
from .controllers import Aplic
from .aia import VERSION,revision
from .spike_device import run as run_device


class Device:
    """Little-endian, 32-bit registers; Detached sources and direct contexts."""
    def __init__(self,config):
        if config.get('spec_version')!=VERSION:raise ValueError('APLIC reference requires AIA-1.0')
        revision(config)
        options=config['aplic'];delegated=config['kind']=='aplic-delegation'
        self.count=options.get('implemented_sources',2);self.child_index=options.get('child_index',0)
        self.bases={'root':options['parent_base'] if delegated else options['base']}
        if delegated:self.bases['child']=options['child_base']
        self.models={name:Aplic(self.count) for name in self.bases}
        self.targets={name:{} for name in self.bases};self.controls={name:0 for name in self.bases};self.contexts={}
        if not 1<=self.count<=1023:raise ValueError('APLIC source count outside model')
        spans=sorted((base,base+0x8000) for base in self.bases.values())
        if any(a[1]>b[0] for a,b in zip(spans,spans[1:])):raise ValueError('APLIC reference control regions overlap')
        for key in ('context','parent_context','child_context'):
            if not 0<=options.get(key,0)<512:raise ValueError('APLIC reference supports context indices 0..511')

    def location(self,address,size):
        if size!=4 or address%4:raise ValueError('APLIC reference requires aligned 32-bit accesses')
        for name,base in self.bases.items():
            if base<=address<base+0x8000:return name,address-base
        raise ValueError('address outside APLIC reference')

    def owns(self,name,source):
        child=self.models['root'].children.get(source)
        return child is self.models[name] if name=='child' else child is None

    def active(self,name,source):
        return 1<=source<=self.count and self.owns(name,source) and self.models[name].mode.get(source,0)==1

    def configure(self,name,source,value):
        if not 1<=source<=self.count:return
        if name=='child' and not self.owns(name,source):return
        model=self.models[name]
        if name=='root':
            old_child=model.children.get(source)
            if value&0x400 and 'child' in self.models:
                if value&0x3ff!=self.child_index:raise ValueError('unmodeled APLIC child index')
                if old_child is self.models['child']:return
                model.configure(source,0);self.targets[name].pop(source,None)
                self.models['child'].configure(source,0);self.targets['child'].pop(source,None)
                model.children[source]=self.models['child']
                return
            if old_child is not None:
                model.children.pop(source);old_child.configure(source,0);self.targets['child'].pop(source,None)
        if value&0x400:value=0  # A leaf cannot delegate.
        mode=value&7
        if mode not in (0,1):raise ValueError('APLIC native reference supports Inactive and Detached sources only')
        was_active=self.active(name,source)
        model.configure(source,mode)
        if mode==0 or not was_active:self.targets[name].pop(source,None)

    def bitmap(self,name,word,register):
        bits=self.models[name].pending if register=='ip' else self.models[name].enabled
        return sum(1<<(s%32) for s in range(word*32,word*32+32) if self.active(name,s) and s in bits)

    def context(self,name,index):
        return self.contexts.setdefault((name,index),dict(delivery=0,force=0,threshold=0))

    def top(self,name,index,claim=False):
        model=self.models[name];ctx=self.context(name,index);eligible=[]
        for source in model.pending&model.enabled:
            if not self.active(name,source):continue
            if source not in self.targets[name]:raise ValueError('APLIC target not initialized')
            target,priority=self.targets[name][source]
            if target==index and (ctx['threshold']==0 or priority<ctx['threshold']):eligible.append(source)
        source=min(eligible,key=lambda s:(self.targets[name][s][1],s),default=0)
        if claim:
            if source:model.pending.discard(source)
            else:ctx['force']=0
        return (source<<16)|self.targets[name][source][1] if source else 0

    def read(self,address,size):
        name,offset=self.location(address,size);model=self.models[name]
        if offset==0:return 0x80000000|self.controls[name]
        if 4<=offset<=0xffc:
            source=offset//4
            if not 1<=source<=self.count:return 0
            if name=='root' and source in model.children:return 0x400|self.child_index
            return model.mode.get(source,0) if self.owns(name,source) else 0
        for base,kind in ((0x1c00,'ip'),(0x1e00,'ie')):
            if base<=offset<base+128:return self.bitmap(name,(offset-base)//4,kind)
        if 0x1d00<=offset<0x1d80 or 0x1f00<=offset<0x1f80:return 0
        if 0x3004<=offset<=0x3ffc:
            source=(offset-0x3000)//4
            if not self.active(name,source):return 0
            if source not in self.targets[name]:raise ValueError('APLIC target not initialized')
            hart,priority=self.targets[name][source];return (hart<<18)|priority
        if 0x4000<=offset<0x8000:
            index,register=divmod(offset-0x4000,32);ctx=self.context(name,index)
            if register in (0,4,8):return ctx[{0:'delivery',4:'force',8:'threshold'}[register]]
            if register in (0x18,0x1c):return self.top(name,index,register==0x1c)
        raise ValueError('unmodeled APLIC register read')

    def write(self,address,value,size):
        name,offset=self.location(address,size);model=self.models[name]
        if offset==0:
            if value&5:raise ValueError('APLIC reference supports little-endian direct delivery only')
            self.controls[name]=value&0x100;return
        if 4<=offset<=0xffc:self.configure(name,offset//4,value);return
        for base,kind,clear in ((0x1c00,'ip',False),(0x1d00,'ip',True),(0x1e00,'ie',False),(0x1f00,'ie',True)):
            if base<=offset<base+128:
                word=(offset-base)//4;bits=model.pending if kind=='ip' else model.enabled
                for source in range(word*32,word*32+32):
                    if self.active(name,source) and value&(1<<(source%32)):
                        bits.discard(source) if clear else bits.add(source)
                return
        if 0x3004<=offset<=0x3ffc:
            source=(offset-0x3000)//4
            if self.active(name,source):self.targets[name][source]=((value>>18)&0x3fff,max(1,value&255))
            return
        if 0x4000<=offset<0x8000:
            index,register=divmod(offset-0x4000,32);ctx=self.context(name,index)
            if register in (0,4,8):ctx[{0:'delivery',4:'force',8:'threshold'}[register]]=value&(255 if register==8 else 1);return
            if register in (0x18,0x1c):return
        raise ValueError('unmodeled APLIC register write')


def run(directory,scenario,config,timeout,shim_inputs):
    device=Device(config)
    return run_device(directory,scenario,config,timeout,shim_inputs,device=device,
        mmio=[(base,0x8000) for base in device.bases.values()],irq=lambda:0,drive=lambda _:None,
        scope='native Spike ISA with Python APLIC direct/Detached MMIO; no IRQ-line delivery or DUT coverage claim')
