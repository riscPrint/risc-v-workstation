import pytest
from rvw.privilege import campaign
from rvw.privilege.plic_delivery import programs,reference

pytestmark=pytest.mark.fast


def test_delivery_profiles_and_model():
    c=campaign.load('examples/privilege/plic-delivery.json');rows=campaign.scenarios(c)
    assert len(rows)==6 and len({r['id'] for r in rows})==6
    assert all(reference(r)['status']=='pass' for r in rows)
    assert all([e['level'] for e in r['events']]==[False,True,False] for r in rows)
    supervisor=next(r['assembly'] for r in rows if r['id']=='plic-delivery-s-1-global')
    assert 'csrw stvec' in supervisor and 'csrr t0, scause' in supervisor and ' sret' in supervisor
    assert 'finish_ecall:' in supervisor and 'li t1, 9' in supervisor
    machine=next(r['assembly'] for r in rows if r['id']=='plic-delivery-m-0-local')
    assert 'csrr t0, mcause' in machine and ' mret' in machine
    assert 'bnez s0, fail' in machine and 'irq_pending_wait:' in machine


def test_target_validation():
    c=campaign.load('examples/privilege/plic-delivery.json');c['plic_delivery']['targets'][0]['context']=2
    with pytest.raises(ValueError,match='target'):programs(c)


def test_interrupt_before_claim_does_not_commit_the_preview(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from rvw.privilege import spike_plic,spike_device
    instances=[]
    class Device:
        def __init__(self,layout):self.reads=0;instances.append(self)
        def irq(self,context):return True
        def read(self,address,size):self.reads+=1;return 42
    class CPU:
        def __init__(self,*a,**kw):
            self.count=0;self.regs=[0]*32;self.regs[1]=0x200004
            self.elf=SimpleNamespace(entry=0x80000000,symbols={'stimulus_step':8,'stimulus_ack':24,'tohost':16})
            self.lib=SimpleNamespace(rvw_read_physical=self.read);self.handle=1
        def read(self,handle,address,out):
            out._obj.value=(int(self.count==2) if address==16 else 0 if address==8 else 0x0000a103)
            return 0
        def step(self,interrupt,mmio):
            assert interrupt==(1<<63)|11 and mmio==(0x200004,42)
            self.count+=1
            return dict(pc=0x80000000,pc_next=0x80000000+4*(self.count==2),trap=self.count==1,
                        intr=self.count==1,cause=(1<<63)|11,mem_rmask=15 if self.count==2 else 0,
                        mem_wmask=0,mem_fault=0,mem_addr=0x200004)
        def close(self):pass
    monkeypatch.setattr(spike_plic,'Plic',Device);monkeypatch.setattr(spike_device,'Spike',CPU)
    layout=dict(priority=0x1000,pending=0x2000,enable=0x3000,enable_stride=128,context=0x200000,context_stride=4096,sources=1,contexts=1)
    scenario=dict(id='plic-delivery-m-0-global',elf='one.elf',events=[],reference_model=dict(layout=layout,context=0))
    result=spike_plic.run(tmp_path,scenario,{},2,{'library':{'sha256':'shim'},'manifest':{'sha256':'manifest'}})
    assert result['status']=='pass' and result['instructions']==2
    assert instances[0].reads==1


def test_reference_registry_labels_and_hashes_the_actual_models(tmp_path):
    import json
    c=campaign.load('examples/privilege/plic-delivery.json')
    scenario=programs(c)[0];scenario.pop('assembly')
    elf=tmp_path/'one.elf';elf.write_bytes(b'elf fixture')
    scenario.update(elf=elf.name,elf_sha256=campaign.digest(elf))
    path=tmp_path/'manifest.json'
    manifest=dict(schema='rvw.privilege-build/1',config=c,scenarios=[scenario])
    path.write_text(json.dumps(manifest))
    result=campaign.reference(tmp_path)
    assert result['status']=='pass' and result['evidence']=='model-based'
    assert 'no DUT coverage' in result['scope']
    assert set(result['model_sha256'])=={'controllers.py','plic_delivery.py','devices.py'}
    scenario['reference_model']['kind']='unknown'
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='no Python reference'):campaign.reference(tmp_path)
