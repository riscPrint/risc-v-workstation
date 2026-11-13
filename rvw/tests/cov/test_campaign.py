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
    compiler=tmp_path/'cc';compiler.write_text('fixture compiler')
    monkeypatch.setattr(c.shutil,'which',lambda _:str(compiler))
    monkeypatch.setattr(c, 'plan', lambda *a: {'isa_plan': {}, 'groups':[{'name':'g','bins':[[1],[2],[3]]}]})
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
    monkeypatch.setattr(c, 'qualify', lambda *a: {'status':'qualified', 'execution_identity':'fixture-native', 'coverage':{
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


def test_generator_profile_does_not_add_undeclared_semantic_bins(tmp_path,monkeypatch):
    settings=setup(tmp_path,monkeypatch)
    monkeypatch.setattr(c,'plan',lambda *a:{'isa_plan':{},'groups':[{'name':'other','bins':[[9]]}]})
    result=c.campaign(settings,tmp_path/'out')
    assert result['supported_bins']==0 and result['generation_profile_bins']==2
    assert result['full_plan_bins']==1 and result['attempts']==[]
    assert result['generation_groups']==[{'group':'other','declared_bins':1,'supported_bins':0}]


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


@pytest.mark.parametrize('status',['fail','assert','rvfi_error','timeout'])
def test_conclusive_c1_failures_stop_campaign(tmp_path,monkeypatch,status):
    result=tmp_path/'run/result.json';result.parent.mkdir();result.write_text('{}')
    run=SimpleNamespace(elf_sha256='a'*64,status=status,why_inconclusive=None)
    monkeypatch.setattr(c,'payload',lambda *a:{'elf_sha256':'a'*64})
    monkeypatch.setattr(c,'load_run',lambda *a:run)
    assert c.qualify('elf',result.parent,'platform','manifest','root',{})['status']=='core_failure'


def test_sequence_settings_use_same_verifier_and_keep_denominator(tmp_path,monkeypatch):
    settings=setup(tmp_path,monkeypatch)
    data=json.loads(settings.read_text());data.update(sequences={'distances':[1],'kinds':['RAW']},attempts=1)
    settings.write_text(json.dumps(data))
    seen=[]
    def qualify(*args):
        seen.append(args[5])
        assert args[6].is_file()
        return {'status':'qualified','execution_identity':'fixture-native','coverage':{'groups':{}}}
    monkeypatch.setattr(c,'qualify',qualify)
    result=c.campaign(settings,tmp_path/'out')
    assert result['attempts'][0]['goal']=='sequence:["RAW",1]'
    assert len(seen[0]['instructions'])==2
    assert result['full_plan_bins']==4 and result['supported_bins']==3


def test_rtl_pending_goal_retries_after_isa_saturation(tmp_path,monkeypatch):
    from rvw.cov import feedback_campaign as feedback
    from rvw.cov.rtl import identity
    settings=setup(tmp_path,monkeypatch)
    plan={'schema':'rvw.rtl-plan/1','design':'a'*64,
          'clock':{'signal':'TOP.c','edge':'rising','sampling':'pre-edge'},
          'reset':{'signal':'TOP.r','active':1,'rule':'disable-clear'},
          'signals':{s:{'width':1,'type':'Bool','scala':None} for s in ('TOP.c','TOP.r')},
          'bins':[{'id':'event','kind':'event','domain':'speculative','when':{'TOP.r':[0]}}]}
    recipes={'schema':'rvw.event-recipes/1','plan_id':identity(plan),'design':plan['design'],
             'recipes':[{'goal':'g:[1]','targets':['event']}]}
    (tmp_path/'rtl.json').write_text(json.dumps(plan));(tmp_path/'recipes.json').write_text(json.dumps(recipes))
    data=json.loads(settings.read_text());data.update(rtl_plan='rtl.json',recipes='recipes.json')
    settings.write_text(json.dumps(data))
    monkeypatch.setattr(c,'qualify',lambda *a:{'status':'qualified','execution_identity':'fixture-native','coverage':{'groups':{'g':{
        'hits':[{'bin':[1],'count':1},{'bin':[2],'count':1}]}}}})
    def collect(guide,goal,*args):
        record={'goal':goal,'samples':[str(len(guide.history))],
                'new_events':['event'] if guide.history else []}
        guide.history.append(record)
        return record
    monkeypatch.setattr(feedback,'collect',collect)
    result=c.campaign(settings,tmp_path/'out')
    assert len(result['attempts'])==2
    assert [a['goal'] for a in result['attempts']]==['g:[1]','g:[1]']
    assert result['guidance_history'][-1]['new_events']==['event']


def test_changed_native_identity_cannot_add_hits(tmp_path,monkeypatch):
    settings=setup(tmp_path,monkeypatch);calls=[]
    def qualify(*args):
        calls.append(1);number=len(calls)
        return {'status':'qualified','execution_identity':'model-'+str(number),
                'coverage':{'groups':{'g':{'hits':[{'bin':[number],'count':1}]}}}}
    monkeypatch.setattr(c,'qualify',qualify)
    result=c.campaign(settings,tmp_path/'out')
    assert result['hits']==['g:[1]']
    assert result['attempts'][1]['status']=='identity_error'
    assert result['attempts'][1]['new_hits']==[]


def test_sealed_raw_attempt_is_verified_on_resume(tmp_path,monkeypatch):
    from rvw.results.generation import open_generation
    settings=setup(tmp_path,monkeypatch)
    monkeypatch.setattr(c,'qualify',lambda *a:{'status':'inconclusive','new_hits':[]})
    result=c.campaign(settings,tmp_path/'out')
    attempt=result['attempts'][0];seal=attempt['sealed_generation']
    generation=open_generation(tmp_path/'out'/seal['store'],seal['id'])
    name=next(iter(attempt['artifacts']))
    assert generation.read_bytes(name)==(tmp_path/'out'/name).read_bytes()
    (generation.path/name).chmod(0o600)
    (generation.path/name).write_text('changed')
    with pytest.raises(ValueError):
        c.campaign(settings,tmp_path/'out',resume=True)


def test_qualifier_supplies_c1_core_to_public_cosim_api(tmp_path,monkeypatch):
    result=tmp_path/'run/result.json';result.parent.mkdir();result.write_text('{}')
    run=SimpleNamespace(core='project-owned-core',elf_sha256='a'*64,status='pass',instret=2,
                        why_inconclusive=None,artifact=lambda _:tmp_path/'trace')
    monkeypatch.setattr(c,'payload',lambda *a:{'elf_sha256':'a'*64})
    monkeypatch.setattr(c,'load_run',lambda *a:run)
    seen=[]
    def compare(*args,**kwargs):
        seen.append(kwargs['core']);return {'status':'inconclusive'}
    monkeypatch.setattr(c,'cosim',compare)
    c.qualify('elf',result.parent,'platform','manifest','root',{})
    assert seen==['project-owned-core']


def test_initial_inputs_are_archived_with_campaign_identity(tmp_path,monkeypatch):
    import json
    from rvw.results.generation import open_generation
    settings=setup(tmp_path,monkeypatch)
    monkeypatch.setattr(c,'qualify',lambda *a:{'status':'inconclusive','new_hits':[]})
    result=c.campaign(settings,tmp_path/'out')
    seal=result['input_generation'];generation=open_generation(tmp_path/'out'/seal['store'],seal['id'])
    record=json.loads(generation.read_bytes('inputs.json'))
    assert record['identity']==result['identity']
    assert record['capture']['files']
    for row in record['capture']['files']:
        assert generation.read_bytes('input-capture/'+row['copy'])


def test_complete_match_without_native_identity_retains_reference_but_no_hits(tmp_path,monkeypatch):
    result=tmp_path/'run/result.json';result.parent.mkdir();result.write_text('{}')
    run=SimpleNamespace(core='fixture',config='test',tools={},source={},extra={},elf_sha256='a'*64,
                        status='pass',instret=1,why_inconclusive=None,artifact=lambda _:tmp_path/'trace')
    monkeypatch.setattr(c,'payload',lambda *a:{'elf_sha256':'a'*64})
    monkeypatch.setattr(c,'load_run',lambda *a:run)
    comparison={'status':'match','trace_complete':True,'end_status':'pass','instructions':1}
    monkeypatch.setattr(c,'cosim',lambda *a,**kw:comparison)
    report=c.qualify('elf',result.parent,'platform','manifest','root',{})
    assert report['status']=='identity_error' and report['new_hits']==[]
    assert report['comparison']==comparison


def test_replay_uses_archived_elf_and_preserves_original_state(tmp_path,monkeypatch):
    settings=setup(tmp_path,monkeypatch);seen=[]
    def qualify(*args):
        seen.append(args[0])
        return {'status':'qualified','execution_identity':'fixture-native','coverage':{
            'groups':{'g':{'hits':[{'bin':[1],'count':1},{'bin':[2],'count':1}]}}}}
    monkeypatch.setattr(c,'qualify',qualify)
    out=tmp_path/'out';original=c.campaign(settings,out)
    pointer=(out/'state/current').read_bytes()
    replay=c.campaign(settings,out,replay=0)
    assert replay['status']=='qualified' and replay['same_execution_identity'] is True
    assert replay['credited_new_hits']==[] and replay['sealed_generation']
    assert (out/'state/current').read_bytes()==pointer
    assert seen[0]!=seen[-1] and 'attempt-evidence' in seen[-1].parts
    assert original['hits']==['g:[1]','g:[2]']


def test_replay_changed_context_is_not_qualified(tmp_path,monkeypatch):
    settings=setup(tmp_path,monkeypatch)
    def evidence(identity):
        return {'status':'qualified','execution_identity':identity,'coverage':{'groups':{'g':{
            'hits':[{'bin':[1],'count':1},{'bin':[2],'count':1}]}}}}
    monkeypatch.setattr(c,'qualify',lambda *a:evidence('old'))
    out=tmp_path/'out';c.campaign(settings,out)
    monkeypatch.setattr(c,'qualify',lambda *a:evidence('new'))
    replay=c.campaign(settings,out,replay=0)
    assert replay['status']=='identity_error' and replay['same_execution_identity'] is False
    assert replay['credited_new_hits']==[]


def test_no_elf_attempt_cannot_execute_replay(tmp_path,monkeypatch):
    settings=setup(tmp_path,monkeypatch)
    monkeypatch.setattr(c,'generate',lambda *a:{'status':'unsupported'})
    out=tmp_path/'out';c.campaign(settings,out)
    assert c.campaign(settings,out,replay=0)['status']=='unsupported'


def test_replay_cli_and_mcp_reject_negative_index(tmp_path):
    import subprocess,sys
    from rvw.cov.campaign_cli import execute_json
    ran=subprocess.run([sys.executable,'-m','rvw','cov','campaign','--settings','unused',
        '--work-dir',str(tmp_path/'unused'),'--replay','-1','--json'],capture_output=True,text=True)
    assert ran.returncode==2,ran.stderr
    with pytest.raises(ValueError) as error:
        execute_json(settings='unused',work_dir=tmp_path/'unused',replay=-1)
    assert json.loads(ran.stdout)['message']==str(error.value)


def test_replay_never_uses_altered_working_elf(tmp_path,monkeypatch):
    settings=setup(tmp_path,monkeypatch);seen=[]
    def qualify(*args):
        seen.append(args[0].read_bytes())
        return {'status':'qualified','execution_identity':'fixture-native','coverage':{
            'groups':{'g':{'hits':[{'bin':[1],'count':1},{'bin':[2],'count':1}]}}}}
    monkeypatch.setattr(c,'qualify',qualify)
    out=tmp_path/'out';c.campaign(settings,out)
    (out/'attempt-0000/elfs/program.elf').write_bytes(b'altered')
    result=c.campaign(settings,out,replay=0)
    assert result['status']=='qualified' and seen[-1]==b'fake elf'
    with pytest.raises(ValueError,match='resume artifact changed'):
        c.campaign(settings,out,resume=True)

def test_campaign_captures_code_template_before_attempts(tmp_path,monkeypatch):
    from rvw.cov import code
    from rvw.cov.rtl import identity
    from rvw.results.generation import open_generation
    settings=setup(tmp_path,monkeypatch)
    (tmp_path/'tiny.v').write_text('module tiny; endmodule\n')
    dat=tmp_path/'baseline.dat';dat.write_text("C '\x01f\x02tiny.v\x01l\x021\x01t\x02line' 7\n")
    database=code.merge(['base='+str(dat)],root=tmp_path)
    db=tmp_path/'db.json';db.write_text(json.dumps(database))
    point=database['points'][0]['id']
    plan={'schema':'rvw.code-goals/1','design':'a'*64,'database':'db.json','database_sha256':c.digest(db)}
    config=tmp_path/'code-plan.json';config.write_text(json.dumps(plan))
    recipes=tmp_path/'recipes.json';recipes.write_text(json.dumps({
        'schema':'rvw.event-recipes/1','plan_id':identity(plan),'design':plan['design'],
        'recipes':[{'goal':'g:[1]','targets':[point]}]}))
    data=json.loads(settings.read_text());data.update(code_plan=config.name,recipes=recipes.name)
    settings.write_text(json.dumps(data))
    monkeypatch.setattr(c,'generate',lambda *a:{'status':'unsupported'})
    report=c.campaign(settings,tmp_path/'out')
    assert report['guidance_coverage']['kind']=='code'
    assert report['guidance_coverage']['unobserved']==[point]
    assert len(report['attempts'])==data['attempts']
    seal=report['input_generation'];generation=open_generation(tmp_path/'out'/seal['store'],seal['id'])
    inputs=json.loads(generation.read_bytes('inputs.json'))
    assert any(row['resolved']==str((tmp_path/'db.json').resolve()) for row in inputs['capture']['files'])
    (tmp_path/'db.json').write_text('{}')
    with pytest.raises(ValueError,match='database hash'):
        c.campaign(settings,tmp_path/'out',resume=True)
