import hashlib
import json
from pathlib import Path
import struct
from types import SimpleNamespace
import pytest
import rvw.memory.concurrent_campaign as campaign
from rvw.cosim.trace import HEX,INT,BOOL
from rvw.memory.axiomatic import check
from rvw.memory.multihart import images
from rvw.memory.commands.concurrent_run import mcp_tools

pytestmark=pytest.mark.fast


def environment(tmp_path,monkeypatch,mode='allowed'):
    adapter=tmp_path/'adapter'
    adapter.write_text('#!/bin/sh\nexit 99\n'); adapter.chmod(0o755)
    calls=[]; saved={}
    def build(root,seed,harts,length,gcc,**kw):
        root=Path(root); root.mkdir(parents=True)
        rows=[]; args=[]
        for h in range(harts):
            entry=0x1000+h*0x1000
            raw=bytearray(136); raw[:6]=b'\x7fELF\x02\x01'
            struct.pack_into('<HH',raw,16,2,243)
            struct.pack_into('<QQQ',raw,24,entry,64,0)
            struct.pack_into('<HHHHH',raw,54,56,1,64,0,0)
            struct.pack_into('<IIQQQQQQ',raw,64,1,5,128,entry,entry,8,8,4)
            struct.pack_into('<II',raw,128,0x3003,0x6f)
            file=root/f'h{h}.elf'; file.write_bytes(raw); args.append(f'{h}={file}')
            rows.append(dict(hart=h,entry=hex(entry),completion_pc=hex(entry+4)))
        manifest=images(args)
        image_file=root/'hart-images.json'; image_file.write_text(json.dumps(manifest))
        reference=root/'initial.json'
        reference.write_text(json.dumps(dict(schema='rvw.axiomatic-initial/1',locations=[dict(address='0x0',size=8,value='0x0')])))
        saved.update(manifest=manifest,programs=rows)
        return dict(status='built',hart_images=str(image_file),reference=str(reference),programs=rows)
    def process(command,**kw):
        calls.append((command,kw))
        if 'axiomatic' in command:
            if mode=='checker-timeout':
                return SimpleNamespace(returncode=-9,timed_out=True,stdout='',stderr='')
            trace=command[command.index('--trace')+1]; reference=command[command.index('--reference')+1]
            model=command[command.index('--model')+1]
            answer=check(trace,reference,model)
            code={'allowed':0,'forbidden':1,'inconclusive':3}[answer['status']]
            if mode=='wrong-checker-exit': code=1
            if mode=='wrong-checker-model': answer['model']='ztso'
            return SimpleNamespace(returncode=code,timed_out=False,stdout=json.dumps(answer),stderr='')
        assert command[:3]==['nice','-n','10'] and command[3]==str(adapter)
        assert '--hart-images' in command and '--rvfi-trace' in command
        assert 0 < kw['timeout'] <= 60
        root=Path(command[command.index('--out')+1]); root.mkdir()
        header=dict(schema='rvw.rvfi/2',xlen=64,isa='rv64ima',core='synthetic',config='test',elf='fixture',
                    harts=[0,1],hart_images=saved['manifest']['harts'],memory_dependencies='complete',memory_addresses='physical')
        if mode=='dependencies': header.pop('memory_dependencies')
        rows=[dict(event='reset',hart=h,epoch=0) for h in (0,1)]
        for h in (0,1):
            r={k:'0x0' for k in HEX}|{k:0 for k in INT}|{k:False for k in BOOL}
            entry=0x1000+h*0x1000; value=1 if mode=='forbidden' else 0
            r.update(hart=h,epoch=0,order='0',mode=3,pc=hex(entry),pc_next=hex(entry+4),insn='0x3003',mem_rmask=255,mem_rdata=hex(value),
                     memory_model=dict(id=f'h{h}-r',hart=h,order=0,kind='R',address=0,size=8,read=value,addr=[],data=[],ctrl=[]))
            if mode=='instruction': r['insn']='0x13'
            if mode=='entry': r['pc']=hex(entry+4); r['insn']='0x6f'
            if mode=='completion': r['pc_next']=hex(entry)
            rows.append(r)
        rows += [dict(event='hart_end',hart=h,epoch=0,status='pass') for h in (0,1) if mode!='incomplete' or h==0]
        trace=root/'rvfi.jsonl'
        trace.write_text(json.dumps(header)+'\n'+''.join(json.dumps(r|dict(cycle=i,capture_seq=str(i)))+'\n' for i,r in enumerate(rows)))
        primary=saved['manifest']['harts'][0]
        status='fail' if mode=='rtl-fail' else 'pass'
        result=dict(schema='rvw.run/1',status=status,config='test',seed=7,max_cycles=int(command[command.index('--max-cycles')+1]),elf_sha256=primary['elf_sha256'],
                    details=dict(hart_images=saved['manifest']['harts']),artifacts=dict(rvfi_trace='rvfi.jsonl'))
        if mode=='c1-hash': result['elf_sha256']='0'*64
        if mode=='c2-hash': header['hart_images']=[dict(hart=h,elf_sha256='0'*64) for h in (0,1)]; trace.write_text(json.dumps(header)+'\n'+''.join(json.dumps(r|dict(cycle=i,capture_seq=str(i)))+'\n' for i,r in enumerate(rows)))
        if mode=='input-replaced': Path(primary['elf']).write_bytes(b'replaced after capture')
        (root/'result.json').write_text(json.dumps(result))
        return SimpleNamespace(returncode=1 if mode=='adapter-exit' else 0,timed_out=mode=='adapter-timeout',stdout='',stderr='')
    monkeypatch.setattr(campaign,'build',build)
    monkeypatch.setattr(campaign,'run_group',process)
    return adapter,calls


@pytest.mark.parametrize('model',['rvwmo','ztso'])
def test_generated_capture_feeds_the_actual_checker(tmp_path,monkeypatch,model):
    adapter,calls=environment(tmp_path,monkeypatch)
    report=campaign.run(tmp_path/'run',adapter,'test',seed=7,model=model)
    assert report['status']=='allowed' and report['axiomatic']['model']==model
    assert report['capture']['retirements']==2 and len(calls)==2
    assert json.loads((tmp_path/'run/campaign.json').read_text())['status']=='allowed'
    assert mcp_tools()[0].name=='memory_concurrent_run'


@pytest.mark.parametrize('mode,status,stage',[
    ('forbidden','forbidden','axiomatic'),('dependencies','inconclusive','axiomatic'),
    ('incomplete','inconclusive','axiomatic'),('instruction','inconclusive','capture'),
    ('entry','inconclusive','capture'),('completion','inconclusive','capture'),
    ('c1-hash','inconclusive','capture'),('c2-hash','inconclusive','capture'),
    ('adapter-exit','inconclusive','adapter'),('adapter-timeout','inconclusive','adapter'),
    ('rtl-fail','fail','adapter'),('checker-timeout','inconclusive','axiomatic'),
    ('wrong-checker-exit','inconclusive','axiomatic'),('wrong-checker-model','inconclusive','axiomatic')])
def test_missing_or_bad_evidence_cannot_produce_allowed(tmp_path,monkeypatch,mode,status,stage):
    adapter,calls=environment(tmp_path,monkeypatch,mode)
    report=campaign.run(tmp_path/'run',adapter,'test',seed=7)
    assert report['status']==status and report['stage']==stage,report
    if stage!='axiomatic': assert len(calls)==1


def test_capture_uses_prelaunch_elf_bytes(tmp_path,monkeypatch):
    adapter,_=environment(tmp_path,monkeypatch,'input-replaced')
    assert campaign.run(tmp_path/'run',adapter,'test',seed=7)['status']=='allowed'


def test_missing_adapter_does_not_build_or_create_output(tmp_path,monkeypatch):
    monkeypatch.setattr(campaign.shutil,'which',lambda path:None)
    report=campaign.run(tmp_path/'absent','missing-adapter','test')
    assert report['status']=='inconclusive' and not report['adapter_invoked']
    assert not (tmp_path/'absent').exists()


def test_failed_build_does_not_invoke_adapter(tmp_path,monkeypatch):
    adapter,calls=environment(tmp_path,monkeypatch)
    monkeypatch.setattr(campaign,'build',lambda *a,**kw:dict(status='inconclusive',reason='seeded build failure'))
    report=campaign.run(tmp_path/'failed',adapter,'test')
    assert report['status']=='inconclusive' and not calls and not report['adapter_invoked']


def test_total_campaign_budget_stops_before_adapter_launch(tmp_path,monkeypatch):
    adapter,calls=environment(tmp_path,monkeypatch)
    ticks=iter([0,0,61])
    monkeypatch.setattr(campaign,'time',SimpleNamespace(monotonic=lambda:next(ticks)))
    report=campaign.run(tmp_path/'expired',adapter,'test',seed=7)
    assert report['status']=='inconclusive' and not calls and not report['adapter_invoked']
    assert 'timeout' in report['reason']
