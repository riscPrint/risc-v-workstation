import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import pytest
from rvw.privilege import campaign,model_observe

pytestmark=pytest.mark.fast


def fixture(tmp_path,monkeypatch,profile='fast-preemption'):
    c=campaign.load('examples/privilege/'+profile+'.json');scenario=campaign.scenarios(c)[0]
    elf=tmp_path/'one.elf';elf.write_bytes(b'ELF fixture')
    scenario.update(elf=elf.name,elf_sha256=campaign.digest(elf),stimulus_sha256='1'*64)
    symbols={b['symbol']:0x80000000+4*i for i,b in enumerate(scenario['model_bindings'])}
    symbols['vector_wait']=0x80002000
    segments=[];rows=[]
    def append(pc,insn,value,rd=5):
        row=dict(order=len(rows),cycle=len(rows),mode=3,rs1=0,rs2=0,rd=rd,mem_rmask=0,mem_wmask=0,
                 trap=False,intr=False,halt=False,mem_fault=False,pc=hex(pc),pc_next=hex(pc+4),insn=hex(insn),
                 rs1_rdata='0x0',rs2_rdata='0x0',rd_wdata=hex(value),mem_addr='0x0',mem_rdata='0x0',mem_wdata='0x0')
        rows.append(row)
    for b in scenario['model_bindings']:
        pc=symbols[b['symbol']];insn=(int(b['csr'],0)<<20)|(2<<12)|(5<<7)|0x73
        segments.append((pc,insn.to_bytes(4,'little'),4))
        for value in b['expected']:
            value=symbols[value['symbol']] if isinstance(value,dict) else int(value,0)
            append(pc,insn,value)
    for address in scenario.get('model_required_pcs',[]):
        pc=int(address,0);segments.append((pc,(0x13).to_bytes(4,'little'),4));append(pc,0x13,0,0)
    monkeypatch.setattr(model_observe,'Elf',lambda _:SimpleNamespace(xlen=64,symbols=symbols,segments=segments))
    header=dict(schema='rvw.rvfi/1',xlen=64,isa=c['isa'],core='fixture',config='fixture',elf='one.elf',elf_sha256=scenario['elf_sha256'])
    path=tmp_path/'trace.jsonl'
    def write(data=None,end=True):
        data=rows if data is None else data
        records=[header,*data]+([dict(event='end',cycle=len(data)+1,status='pass')] if end else [])
        path.write_text(''.join(json.dumps(x)+'\n' for x in records))
    write();return elf,scenario,path,rows,write


def test_complete_bound_values_and_missing_or_wrong_values(tmp_path,monkeypatch):
    elf,s,path,rows,write=fixture(tmp_path,monkeypatch)
    result=model_observe.observe(elf,s,path)
    assert result['status']=='pass' and result['evidence']=='model-based' and result['observations']==10
    write(end=False);assert model_observe.observe(elf,s,path)['status']=='inconclusive'
    data=deepcopy(rows);data[0]['rd_wdata']='0x0';write(data)
    assert model_observe.observe(elf,s,path)['status']=='fail'
    data=deepcopy(rows);data[0]['insn']='0x13';write(data)
    assert model_observe.observe(elf,s,path)['status']=='inconclusive'
    write();s['model_bindings'][0]['expected']=['0x0']
    assert model_observe.observe(elf,s,path)['status']=='inconclusive'


def test_vector_pc_and_symbolic_exception_pc_are_required(tmp_path,monkeypatch):
    elf,s,path,rows,write=fixture(tmp_path,monkeypatch,'fast-vector')
    assert model_observe.observe(elf,s,path)['status']=='pass'
    data=deepcopy(rows);data[-1]['trap']=True;write(data)
    assert model_observe.observe(elf,s,path)['status']=='inconclusive'
    write();s['spec_version']='old-clic-draft'
    assert model_observe.observe(elf,s,path)['status']=='inconclusive'


def test_model_pass_does_not_earn_complete_architectural_groups(tmp_path,monkeypatch):
    import rvw.results
    elf,s,path,rows,write=fixture(tmp_path,monkeypatch)
    manifest=dict(schema='rvw.privilege-build/1',config={},scenarios=[s])
    (tmp_path/'manifest.json').write_text(json.dumps(manifest));(tmp_path/'result.json').write_text('{}')
    run=SimpleNamespace(elf_sha256=campaign.digest(elf),path=tmp_path,why_inconclusive=None,status='pass',
                        core='fixture',config='fixture',artifacts={'rvfi_trace':path.name},extra={'stimulus_sha256':'1'*64})
    monkeypatch.setattr(rvw.results,'load_run',lambda _:run)
    monkeypatch.setattr(campaign,'run_group',lambda *a,**kw:pytest.fail('unsupported strict ISA model must not run'))
    checked=campaign.check(tmp_path,tmp_path,'platform.json')
    assert checked['status']=='inconclusive' and checked['counts']['pass']==0
    assert checked['model_counts']['pass']==1 and list(checked['model_groups'].values())==['pass']
    data=deepcopy(rows);data[0]['rd_wdata']='0x0';write(data)
    checked=campaign.check(tmp_path,tmp_path,'platform.json')
    assert checked['status']=='fail' and checked['model_counts']['fail']==1
    path.unlink();run.status='fail'
    assert campaign.check(tmp_path,tmp_path,'platform.json')['model_counts']['fail']==1


@pytest.mark.parametrize('backend,profile,module',[('spike-python-reri','reri-transactions','spike_reri'),('spike-python-plic','plic-delivery','spike_plic')])
def test_native_device_backend_routes_to_its_own_module(tmp_path,monkeypatch,backend,profile,module):
    import importlib
    import rvw.cosim.spike
    c=campaign.load('examples/privilege/'+profile+'.json');c.update(reference_backend=backend,reference_shim='fixture')
    s=campaign.scenarios(c)[0];s.pop('assembly');elf=tmp_path/'one.elf';elf.write_bytes(b'fixture')
    s.update(elf=elf.name,elf_sha256=campaign.digest(elf));(tmp_path/'manifest.json').write_text(json.dumps(dict(schema='rvw.privilege-build/1',config=c,scenarios=[s])))
    calls=[]
    def run(*args):calls.append(args);return dict(id=s['id'],status='pass',evidence='model-based')
    monkeypatch.setattr(importlib.import_module('rvw.privilege.'+module),'run',run)
    monkeypatch.setattr(rvw.cosim.spike,'capture_shim',lambda *a:{'fixture':True})
    result=campaign.reference(tmp_path)
    assert result['status']=='pass' and len(calls)==1 and calls[0][-1]=={'fixture':True}


def test_reference_or_unbound_trace_cannot_earn_c1_model_groups(tmp_path,monkeypatch):
    elf,s,path,rows,write=fixture(tmp_path,monkeypatch)
    identity=dict(core='fixture',config='fixture')
    assert model_observe.observe(elf,s,path,c1_identity=identity)['status']=='pass'
    records=[json.loads(line) for line in path.read_text().splitlines()]
    records[0]['evidence']='model-based'
    path.write_text(''.join(json.dumps(x)+'\n' for x in records))
    assert model_observe.observe(elf,s,path,c1_identity=identity)['status']=='inconclusive'
    write()
    assert model_observe.observe(elf,s,path,c1_identity=dict(core='other',config='fixture'))['status']=='inconclusive'


def test_model_groups_require_every_member_even_without_bindings(tmp_path,monkeypatch):
    import rvw.results
    elf,s,path,rows,write=fixture(tmp_path,monkeypatch)
    other=tmp_path/'other.elf';other.write_bytes(b'other fixture')
    second=dict(id='missing',elf=other.name,elf_sha256=campaign.digest(other),bins=s['bins'])
    (tmp_path/'manifest.json').write_text(json.dumps(dict(schema='rvw.privilege-build/1',scenarios=[s,second])))
    (tmp_path/'result.json').write_text('{}')
    run=SimpleNamespace(elf_sha256=campaign.digest(elf),path=tmp_path,why_inconclusive=None,status='pass',core='fixture',config='fixture',
                        artifacts={'rvfi_trace':path.name},extra={'stimulus_sha256':'1'*64})
    monkeypatch.setattr(rvw.results,'load_run',lambda _:run)
    result=campaign.check(tmp_path,tmp_path,'platform.json')
    assert result['model_counts']['pass']==0 and result['model_counts']['inconclusive']==1
