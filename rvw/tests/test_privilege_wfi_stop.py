from copy import deepcopy
import json
from types import SimpleNamespace
import pytest
from rvw.privilege import campaign,wfi_stop
from rvw.privilege.events import MailboxDriver

pytestmark=pytest.mark.fast


def event():return campaign.scenarios(campaign.load('examples/privilege/wfi-stop.json'))[0]['events'][0]


def sample(running=False,pending=False,retired=9):
    return dict(clock_running=running,pending=pending,retired=retired,wfi_active=not running,wfi_pc=0x80000100,state=dict(retained_gpr=0x12345))


def capture():
    e=event();d=wfi_stop.StopWakeDriver(e,dict(wfi_site=0x80000100));drives=[];acks=[]
    for tick in range(11):
        s=sample(running=tick==0 or tick>=6,pending=5<=tick<=8,retired=10 if tick>=7 else 9)
        d.service(2 if tick>=7 else 1,drives.append,acks.append,tick=tick,snapshot=s)
    assert d.complete and acks==[2]
    assert [x['asserted'] for x in drives]==[True,False]
    assert d.asserted==4 and d.cleared==8
    return e,d.capture()


def test_gated_stop_input_and_retention():
    e,c=capture();assert wfi_stop.observe(e,c,0x80000100)['status']=='pass'
    with pytest.raises(ValueError,match='StopWakeDriver'):MailboxDriver([e])
    bad=deepcopy(c);bad['samples'][3]['retired']=10
    assert wfi_stop.observe(e,bad,0x80000100)['status']=='fail'
    bad=deepcopy(c);bad['samples'][-1]['state']['retained_gpr']^=1
    assert wfi_stop.observe(e,bad,0x80000100)['status']=='fail'
    bad=deepcopy(c);bad['samples'].pop(2)
    assert wfi_stop.observe(e,bad,0x80000100)['status']=='inconclusive'
    assert wfi_stop.observe(e,c,0x80000104)['status']=='fail'


def test_early_wfi_return_does_not_trigger_input_or_require_architectural_sleep():
    e=event();d=wfi_stop.StopWakeDriver(e,dict(wfi_site=0x80000100));drives=[]
    for tick in range(8):d.service(1,drives.append,lambda _:None,tick=tick,snapshot=sample(running=True))
    assert drives==[] and wfi_stop.observe(e,d.capture(),0x80000100)['status']=='inconclusive'


def test_missing_restart_and_cleanup():
    e=event();d=wfi_stop.StopWakeDriver(e,dict(wfi_site=0x80000100));drives=[]
    for tick in range(24):d.service(1,drives.append,lambda _:None,tick=tick,snapshot=sample(running=tick==0,pending=tick>=5))
    assert wfi_stop.observe(e,d.capture(),0x80000100)['status']=='fail'
    d.close(drives.append);assert drives[-1]['asserted'] is False
    assert wfi_stop.observe(e,d.capture(),0x80000100)['status']=='fail'


def test_callbacks_cannot_mutate_recorded_snapshot():
    e=event();d=wfi_stop.StopWakeDriver(e,dict(wfi_site=0x80000100));s=sample()
    for tick in range(5):d.service(1,lambda _:s['state'].update(retained_gpr=0),lambda _:None,tick=tick,snapshot=s)
    assert d.capture()['samples'][d.asserted]['state']['retained_gpr']==0x12345


def test_program_and_reference_models():
    rows=campaign.scenarios(campaign.load('examples/privilege/wfi-stop.json'))
    assert len(rows)==8 and all(wfi_stop.reference(r)['status']=='pass' for r in rows)
    changed=deepcopy(rows[0]);changed['reference_model']['expected']['trap']=True
    assert wfi_stop.reference(changed)['status']=='fail'
    assert all('wait_release:' in r['assembly'] for r in rows)


def test_c1_without_stop_capture_cannot_earn_model_groups(tmp_path,monkeypatch):
    import rvw.results
    row=campaign.scenarios(campaign.load('examples/privilege/wfi-stop.json'))[0]
    elf=tmp_path/'one.elf';elf.write_bytes(b'elf');(tmp_path/'result.json').write_text('{}')
    row.update(elf=elf.name,elf_sha256=campaign.digest(elf))
    (tmp_path/'manifest.json').write_text(json.dumps(dict(schema='rvw.privilege-build/1',config={},scenarios=[row])))
    run=SimpleNamespace(elf_sha256=row['elf_sha256'],extra={},path=tmp_path,why_inconclusive=None,status='pass',artifacts={})
    monkeypatch.setattr(rvw.results,'load_run',lambda _:run)
    report=campaign.check(tmp_path,tmp_path,'platform.json')
    assert report['scenarios'][0]['wfi_stop']['status']=='inconclusive'
    assert report['model_counts']['pass']==0 and report['counts']['pass']==0
    import rvw.cosim.elf
    monkeypatch.setattr(rvw.cosim.elf,'Elf',lambda _:SimpleNamespace(symbols=dict(wfi_site=0x80000100)))
    e,c=capture();c['samples'][3]['retired']=10
    (tmp_path/'stop.json').write_text(json.dumps(c));run.artifacts['privilege_wfi_stop']='stop.json'
    report=campaign.check(tmp_path,tmp_path,'platform.json')
    assert report['scenarios'][0]['status']=='fail' and report['counts']['fail']==1


def test_failed_drive_can_release_input_without_acknowledgment():
    e=event();d=wfi_stop.StopWakeDriver(e,dict(wfi_site=0x80000100));drives=[];acks=[]
    def drive(action):
        drives.append(action)
        if action['asserted']:raise RuntimeError('project drive failed')
    with pytest.raises(RuntimeError,match='drive failed'):
        for tick in range(5):d.service(1,drive,acks.append,tick=tick,snapshot=sample(running=tick==0))
    d.close(drive)
    assert [v['asserted'] for v in drives]==[True,False] and not acks
    assert not d.capture()['input_applied']
    assert wfi_stop.observe(e,d.capture(),0x80000100)['status']=='inconclusive'


def test_input_is_held_until_software_observes_delivery():
    e=event();d=wfi_stop.StopWakeDriver(e,dict(wfi_site=0x80000100));drives=[];acks=[]
    for tick in range(12):
        d.service(1,drives.append,acks.append,tick=tick,snapshot=sample(running=tick==0 or tick>=6,pending=tick>=5,retired=10 if tick>=7 else 9))
    assert [v['asserted'] for v in drives]==[True] and not acks
    d.service(2,drives.append,acks.append,tick=12,snapshot=sample(running=True,pending=True,retired=10))
    assert drives[-1]['asserted'] is False and acks==[2]
