"""Selection, failed-run accounting and resume must not invent measured hits."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from rvw.cov import campaign as c


def setup(tmp_path, monkeypatch):
    for name in ('manifest','linker','platform','project'):
        (tmp_path/name).write_text('{}')
    (tmp_path/'runtime').write_text('{payload}')
    data = dict(schema='rvw.stimulus-loop/1', manifest='manifest', source_root='.', project='project',
                config='test', registers=[5,6,7], runtime='runtime', linker='linker', platform='platform',
                compiler='cc', isa='rv32i', abi='ilp32', attempts=2, seed=1)
    settings = tmp_path/'settings.json'; settings.write_text(json.dumps(data))
    monkeypatch.setattr(c, 'plan', lambda *a: {'isa_plan': {}, 'groups':[{'bins':[1,2,3]}]})
    monkeypatch.setattr(c, 'profile', lambda *a: {'g:[1]':{}, 'g:[2]':{}})
    monkeypatch.setattr(c, 'load_config', lambda **kw: SimpleNamespace(configs=['test']))
    monkeypatch.setattr(c, 'source_for', lambda *a: None)
    monkeypatch.setattr(c, 'run_plan', lambda *a: None)
    def generate(manifest, root, goal, directory, *args):
        directory.mkdir(); (directory/'payload.S').write_text('.word 0x33')
        return dict(status='generated', source=str(directory/'payload.S'))
    monkeypatch.setattr(c, 'generate', generate)
    def compile(argv, **kwargs):
        Path(argv[-1]).write_bytes(b'fake elf')
        return SimpleNamespace(returncode=0, timed_out=False)
    monkeypatch.setattr(c, 'run_group', compile)
    return settings


def test_feedback_selects_updated_holes_and_resume_validates_artifacts(tmp_path, monkeypatch):
    settings = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(c, 'qualify', lambda *a: {'status':'qualified', 'coverage':{
        'groups':{'g':{'hits':[{'bin':[1], 'count':1}, {'bin':[2], 'count':1}]}}}})
    result = c.campaign(settings, tmp_path/'out')
    assert len(result['attempts']) == 1  # The incidental hit removes the second goal.
    assert result['hits'] == ['g:[1]', 'g:[2]']
    assert result['full_plan_bins'] == 3
    assert result['bins_per_cpu_hour'] is None
    resumed = c.campaign(settings, tmp_path/'out', resume=True)
    assert resumed['hits'] == result['hits']
    artifact = tmp_path/'out/attempt-0000/elfs/program.elf'
    artifact.write_text('changed')
    with pytest.raises(ValueError, match='artifact changed'):
        c.campaign(settings, tmp_path/'out', resume=True)


@pytest.mark.parametrize('status', ['mismatch','inconclusive','core_failure','trace_error'])
def test_unqualified_attempt_earns_no_hits(tmp_path, monkeypatch, status):
    settings = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(c, 'qualify', lambda *a: {'status':status, 'new_hits':[]})
    result = c.campaign(settings, tmp_path/'out')
    assert result['hits'] == []
    assert all('controller_cpu_s' in a for a in result['attempts'])
    assert len(result['attempts']) == (1 if status in ('mismatch','core_failure') else 2)


def test_resume_rejects_changed_runtime(tmp_path, monkeypatch):
    settings = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(c, 'generate', lambda *a: {'status':'unsat'})
    result = c.campaign(settings, tmp_path/'out')
    assert result['hits'] == [] and len(result['attempts']) == 2
    (tmp_path/'runtime').write_text('#changed\n{payload}')
    with pytest.raises(ValueError, match='inputs or plan changed'):
        c.campaign(settings, tmp_path/'out', resume=True)


@pytest.mark.parametrize('comparison', [
    {'status':'match','trace_complete':False,'end_status':'pass','instructions':2},
    {'status':'match','trace_complete':True,'end_status':'pass','instructions':1},
    {'status':'match','trace_complete':True,'end_status':'fail','instructions':2},
    {'status':'match','trace_complete':True,'end_status':'pass','instructions':2,'synchronized':1},
    {'status':'mismatch','instructions':2},
])
def test_qualifier_rejects_prefix_and_synchronization(tmp_path, monkeypatch, comparison):
    result = tmp_path/'run/result.json'; result.parent.mkdir(); result.write_text('{}')
    run = SimpleNamespace(elf_sha256='a'*64, status='pass', instret=2, why_inconclusive=None,
                          artifact=lambda _: tmp_path/'trace', path=result.parent)
    monkeypatch.setattr(c,'payload',lambda *a: {'elf_sha256':'a'*64})
    monkeypatch.setattr(c,'load_run',lambda *a: run)
    monkeypatch.setattr(c,'cosim',lambda *a,**kw: comparison)
    def forbidden(*a,**kw):
        raise AssertionError('unqualified trace reached coverage')
    monkeypatch.setattr(c,'functional',forbidden)
    report = c.qualify('elf',result.parent,'platform','manifest','root',{})
    assert report['new_hits'] == []


def test_payload_word_is_checked_in_executable(tmp_path, monkeypatch):
    elf = tmp_path/'program.elf'; elf.write_bytes(b'elf')
    monkeypatch.setattr(c,'Elf',lambda _: SimpleNamespace(xlen=32,
        symbols={'rvw_payload_start':256,'rvw_payload_end':260}, segments=[(256,b'\x33\0\0\0',4)]))
    assert c.payload(elf,{'xlen':32,'model':{'instruction':0x33}})['ranges'] == [[256,260]]
    with pytest.raises(ValueError, match='differs'):
        c.payload(elf,{'xlen':32,'model':{'instruction':0x13}})
