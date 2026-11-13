"""Native-counter fixtures. No DUT collection or gain over random is claimed."""
import json
import pytest
from rvw.cov import code,feedback_campaign as f
from rvw.cov.guidance import load_guide
from rvw.cov.rtl import identity

pytestmark=pytest.mark.fast


def setup(tmp_path):
    source=tmp_path/'tiny.v';source.write_text('module tiny; endmodule\n')
    key='\x01f\x02tiny.v\x01l\x021\x01t\x02line\x01h\x02TOP.tiny'
    def dat(name,count):
        path=tmp_path/name;path.write_text(f"C '{key}' {count}\n");return path
    baseline=dat('baseline.dat',7)
    database=code.merge(['baseline='+str(baseline)],root=tmp_path)
    db=tmp_path/'db.json';db.write_text(json.dumps(database))
    plan={'schema':'rvw.code-goals/1','design':'a'*64,'database':'db.json','database_sha256':f.digest(db)}
    point=database['points'][0]['id']
    recipes={'schema':'rvw.event-recipes/1','plan_id':identity(plan),'design':plan['design'],
             'recipes':[{'goal':'candidate','targets':[point]}]}
    config=tmp_path/'plan.json';config.write_text(json.dumps(plan))
    recipe_path=tmp_path/'recipes.json';recipe_path.write_text(json.dumps(recipes))
    return config,recipe_path,point,dat


def test_native_code_feedback_uses_exact_universe_and_retains_denominator(tmp_path):
    config,recipes,point,dat=setup(tmp_path);guide=load_guide(config,recipes)
    # Initial template counts do not earn any qualified credit.
    assert guide.coverage_summary({'candidate'})['unobserved']==[point]
    report=code.merge(['new='+str(dat('new.dat',1))],root=tmp_path)
    observed=guide.observe('candidate',report,qualified=True,rtl_sha256='a'*64)
    assert observed['new_events']==[point]
    summary=guide.coverage_summary({'candidate'})
    assert summary['declared_bins']==summary['full_input_bins']==1 and summary['unobserved']==[]
    with pytest.raises(ValueError,match='repeated'):
        guide.observe('candidate',report,qualified=True,rtl_sha256='a'*64)


def test_code_source_and_universe_mutations_cannot_reward(tmp_path):
    config,recipes,_,dat=setup(tmp_path);guide=load_guide(config,recipes)
    report=code.merge(['new='+str(dat('new.dat',1))],root=tmp_path)
    report['point_universe']='wrong'
    with pytest.raises(ValueError,match='universe'):
        guide.observe('candidate',report,qualified=True,rtl_sha256='a'*64)
    report['point_universe']=guide.database['point_universe'];report['sources']['tiny.v']['sha256']='changed'
    with pytest.raises(ValueError,match='source hashes'):
        guide.observe('candidate',report,qualified=True,rtl_sha256='a'*64)
    assert guide.history==[]


def test_c1_code_receipt_drives_real_counter_reader(tmp_path):
    config,recipes,point,dat=setup(tmp_path);guide=load_guide(config,recipes)
    elf=tmp_path/'program.elf';elf.write_bytes(b'elf')
    trace=tmp_path/'rvfi.jsonl';trace.write_text('trace')
    coverage=dat('coverage.dat',1)
    receipt={'elf_sha256':f.digest(elf),'rvfi_sha256':f.digest(trace),'samples_sha256':f.digest(coverage),
             'plan_id':guide.plan_id,'rtl_sha256':guide.design,'reset_at_start':True}
    result=tmp_path/'result.json'
    result.write_text(json.dumps({'schema':'rvw.run/1','status':'pass','elf':str(elf),'elf_sha256':f.digest(elf),
        'artifacts':{'coverage':coverage.name,'rvfi_trace':trace.name},'rtl_sha256':guide.design,
        'details':{'coverage_goals':receipt}}))
    observed=f.collect(guide,'candidate',elf,tmp_path,config,True)
    assert observed['status']=='observed' and observed['new_events']==[point]
    assert observed['report']['point_universe']==guide.database['point_universe']


def test_no_reset_or_stale_receipt_refuses_code_credit(tmp_path):
    config,recipes,_,dat=setup(tmp_path);guide=load_guide(config,recipes)
    elf=tmp_path/'program.elf';elf.write_bytes(b'elf');trace=tmp_path/'rvfi.jsonl';trace.write_text('trace')
    coverage=dat('coverage.dat',1)
    result=tmp_path/'result.json'
    record={'schema':'rvw.run/1','status':'pass','elf':str(elf),'elf_sha256':f.digest(elf),
        'artifacts':{'coverage':coverage.name,'rvfi_trace':trace.name},'rtl_sha256':guide.design,
        'details':{'coverage_goals':{'reset_at_start':1}}}
    result.write_text(json.dumps(record))
    observed=f.collect(guide,'candidate',elf,tmp_path,config,True)
    assert observed['status']=='unsupported' and observed['new_events']==[]
    assert 'reset-at-start' in observed['reason']


def test_template_hash_must_match(tmp_path):
    config,recipes,_,_=setup(tmp_path)
    (tmp_path/'db.json').write_text('{}')
    with pytest.raises(ValueError,match='database hash'):
        load_guide(config,recipes)


def test_template_source_must_match_before_any_attempt(tmp_path):
    config,recipes,_,_=setup(tmp_path)
    (tmp_path/'tiny.v').write_text('module changed; endmodule\n')
    with pytest.raises(ValueError,match='source hash'):
        load_guide(config,recipes)


def test_code_plan_selection_retains_full_native_denominator(tmp_path):
    config,recipes,_,_=setup(tmp_path)
    plan=json.loads(config.read_text());plan['targets']=[]
    recipe=json.loads(recipes.read_text());recipe.update(plan_id=identity(plan),recipes=[])
    config.write_text(json.dumps(plan));recipes.write_text(json.dumps(recipe))
    summary=load_guide(config,recipes).coverage_summary(set())
    assert summary['declared_bins']==0 and summary['full_input_bins']==1

