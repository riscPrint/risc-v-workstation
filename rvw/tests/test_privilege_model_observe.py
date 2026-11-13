import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import pytest
from rvw.privilege import campaign,model_observe

pytestmark=pytest.mark.fast


def fixture(tmp_path,monkeypatch,profile='fast-preemption',select=None):
    c=campaign.load('examples/privilege/'+profile+'.json');scenarios=campaign.scenarios(c);scenario=next(r for r in scenarios if r['id']==select) if select else scenarios[0]
    elf=tmp_path/'one.elf';elf.write_bytes(b'ELF fixture')
    scenario.update(elf=elf.name,elf_sha256=campaign.digest(elf),stimulus_sha256='1'*64)
    symbols={b['symbol']:0x80000000+4*i for i,b in enumerate(scenario['model_bindings'])}
    symbols['vector_wait']=0x80002000
    for b in scenario['model_bindings']:
        for value in b['expected']:
            if isinstance(value,dict) and value['symbol'] not in symbols:symbols[value['symbol']]=0x80003000+4*len(symbols)
    segments=[];rows=[]
    def append(pc,insn,value,rd=5,mode=3,virtual=False):
        row=dict(order=len(rows),cycle=len(rows),mode=mode,rs1=0,rs2=0,rd=rd,mem_rmask=0,mem_wmask=0,
                 trap=False,intr=False,halt=False,mem_fault=False,pc=hex(pc),pc_next=hex(pc+4),insn=hex(insn),
                 rs1_rdata='0x0',rs2_rdata='0x0',rd_wdata=hex(value),mem_addr='0x0',mem_rdata='0x0',mem_wdata='0x0')
        if 'h' in c['isa'].split('_')[0][4:]:
            from rvw.cosim.extensions import H_CSRS
            row.update(fd_valid=False,fd=0,fd_wdata='0x0',fflags='0x0',fcsr='0x0',hypervisor=dict(virtual=virtual,mode_after=mode,virtual_after=virtual,csrs={hex(a):'0x0' for a in H_CSRS},translations=[]))
        rows.append(row)
    for b in scenario['model_bindings']:
        pc=symbols[b['symbol']]
        if b['kind']=='writeback':insn=int(b['insn'],0)
        elif b['kind']=='load':insn=(2<<12)|(5<<7)|3
        else:insn=(int(b['csr'],0)<<20)|((1 if b['kind']=='csr-exchange' else 2)<<12)|(5<<7)|0x73
        segments.append((pc,insn.to_bytes(4,'little'),4))
        for value in b['expected']:
            value=symbols[value['symbol']] if isinstance(value,dict) else int(value,0)
            append(pc,insn,value,rd=(insn>>7)&31,mode=b.get('mode',3),virtual=b.get('virtual',False))
            if b['kind']=='load':rows[-1].update(mem_addr=b['address'],mem_rmask=15,mem_rdata=hex(value))
    for address in scenario.get('model_forbidden_pcs',[]):
        from rvw.privilege.state_hierarchy import PROBES
        plan=scenario['reference_model'];pc=symbols[address['symbol']]
        csr=0x10c+plan['index'] if plan['probe']=='stateen' else PROBES[plan['probe']][1]
        insn=0x00c58553 if plan['probe']=='zfinx-op' else (csr<<20)|(2<<12)|(10<<7)|0x73
        segments.append((pc,insn.to_bytes(4,'little'),4))
    for address in scenario.get('model_required_pcs',[]):
        pc=int(address,0);segments.append((pc,(0x13).to_bytes(4,'little'),4));append(pc,0x13,0,0)
    monkeypatch.setattr(model_observe,'Elf',lambda _:SimpleNamespace(xlen=64,symbols=symbols,segments=segments))
    header=dict(schema='rvw.rvfi/1',xlen=64,isa=c['isa'],core='fixture',config='fixture',elf='one.elf',elf_sha256=scenario['elf_sha256'])
    if 'h' in c['isa'].split('_')[0][4:]:header.update(schema='rvw.rvfi/2',hypervisor=True)
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


def test_stateen_forbidden_instruction_and_guest_mode(tmp_path,monkeypatch):
    elf,s,path,rows,write=fixture(tmp_path,monkeypatch,'stateen-extensions',select='stateen-hierarchy-jvt-0-s-000')
    assert model_observe.observe(elf,s,path)['status']=='pass'
    image=model_observe.Elf(elf);pc=image.symbols['access_site']
    insn=int.from_bytes(next(data for address,data,_ in image.segments if address==pc),'little')
    extra=deepcopy(rows[-1]);extra.update(pc=hex(pc),pc_next=hex(pc+4),insn=hex(insn),order=len(rows),cycle=len(rows),rd=10,rd_wdata='0x0')
    write(rows+[extra]);assert model_observe.observe(elf,s,path)['status']=='fail'
    second=tmp_path/'guest';second.mkdir()
    elf,s,path,rows,write=fixture(second,monkeypatch,'stateen-extensions-h',select='stateen-hierarchy-jvt-0-vs-110')
    assert model_observe.observe(elf,s,path)['status']=='pass'
    rows[-1]['hypervisor']['virtual']=False;rows[-1]['hypervisor']['virtual_after']=False;write()
    assert model_observe.observe(elf,s,path)['status']=='fail'


def test_zfinx_instruction_result_binding(tmp_path,monkeypatch):
    elf,s,path,rows,write=fixture(tmp_path,monkeypatch,'stateen-extensions',select='stateen-hierarchy-zfinx-op-0-s-100')
    assert model_observe.observe(elf,s,path)['status']=='pass'
    rows[-1]['rd_wdata']='0x40000000';write()
    assert model_observe.observe(elf,s,path)['status']=='fail'


def test_denied_instruction_must_match_model_even_without_retirement(tmp_path,monkeypatch):
    elf,s,path,rows,write=fixture(tmp_path,monkeypatch,'stateen-extensions',select='stateen-hierarchy-jvt-0-s-000')
    image=model_observe.Elf(elf);pc=image.symbols['access_site']
    image.segments[:]=[(address,b'\x13\x00\x00\x00' if address==pc else data,size)
                       for address,data,size in image.segments]
    result=model_observe.observe(elf,s,path)
    assert result['status']=='inconclusive' and 'denied instruction differs' in result['reason']


def test_ssstateen_only_observations_and_no_machine_gate(tmp_path,monkeypatch):
    elf,s,path,rows,write=fixture(tmp_path,monkeypatch,'ssstateen-only-h',select='ssstateen-zfinx-0-vu-10')
    result=model_observe.observe(elf,s,path)
    assert result['status']=='pass' and result['evidence']=='model-based'
    assert 'state_hierarchy.py' in result['model_sha256']
    s['reference_model']['machine']=0
    assert model_observe.observe(elf,s,path)['status']=='inconclusive'


@pytest.mark.parametrize('selected',['wfi-stop-3-0','wfi-stop-16-1'])
def test_wfi_wake_expected_instruction_observations(tmp_path,monkeypatch,selected):
    elf,s,path,rows,write=fixture(tmp_path,monkeypatch,'wfi-stop',select=selected)
    assert model_observe.observe(elf,s,path)['status']=='pass'
    rows[0]['rd_wdata']='0x0';write()
    assert model_observe.observe(elf,s,path)['status']=='fail'


@pytest.mark.parametrize('profile',['imsic','imsic-s','imsic-vs','aplic','aplic-msi'])
def test_aia_named_claim_observations(tmp_path,monkeypatch,profile):
    elf,s,path,rows,write=fixture(tmp_path,monkeypatch,profile)
    result=model_observe.observe(elf,s,path)
    assert result['status']=='pass' and result['evidence']=='model-based'
    rows[-1]['rd_wdata']='0x99';write()
    assert model_observe.observe(elf,s,path)['status']=='fail'


def test_imsic_claim_requires_combined_read_and_write(tmp_path,monkeypatch):
    elf,s,path,rows,write=fixture(tmp_path,monkeypatch,'imsic')
    image=model_observe.Elf(elf);pc=image.symbols['imsic_claim_0']
    row=next(r for r in rows if int(r['pc'],0)==pc);insn=int(row['insn'],0)^(3<<12)
    image.segments[:]=[(address,insn.to_bytes(4,'little') if address==pc else data,size) for address,data,size in image.segments]
    row['insn']=hex(insn);write()
    assert model_observe.observe(elf,s,path)['status']=='inconclusive'
