"""Budget selection uses measured costs and never fabricates missing timing."""
import pytest
from rvw.cov.smoke import select
pytestmark=pytest.mark.fast


def test_budget_selects_new_coverage_per_cost():
    r=select({'slow':{'a','b','c'},'a':{'a','b'},'b':{'c'}},{'slow':10,'a':2,'b':2},6,1)
    assert r['selected']==['a','b'] and r['covered']==['a','b','c']
    assert r['estimated_total_s']==5


def test_missing_cost_does_not_become_free_execution():
    r=select({'unknown':{'a'},'known':{'b'}},{'known':2},3)
    assert r['selected']==['known'] and r['unknown_costs']==['unknown']


def test_startup_can_consume_budget():
    assert select({'a':{'a'}},{'a':1},3,3)['selected']==[]


@pytest.mark.parametrize('budget',[0,-1,float('nan'),float('inf')])
def test_invalid_budget_is_rejected(budget):
    with pytest.raises(ValueError):select({'a':{'a'}},{'a':1},budget)


def test_cli_registers_with_global_project_option(capsys):
    from rvw.cli import main
    with pytest.raises(SystemExit) as stopped:
        main(['cov','smoke','--help'])
    assert stopped.value.code==0
    assert '--budget-s' in capsys.readouterr().out


@pytest.mark.parametrize('native_status,timed_out,expected',[('pass',True,'timed_out'),('fail',False,'fail')])
def test_deadline_and_c1_failure_cannot_become_pass(tmp_path,monkeypatch,native_status,timed_out,expected):
    import importlib,json
    from hashlib import sha256
    from types import SimpleNamespace
    module=importlib.import_module('rvw.cov.smoke')
    elf=tmp_path/'program';elf.write_bytes(b'unit fixture')
    old={'schema':'rvw.run/1','status':'pass','core':'fixture','config':'test','elf':str(elf),
         'elf_sha256':sha256(elf.read_bytes()).hexdigest(),'seed':1,'max_cycles':100,'mem_latency':0,
         'cycles':1,'instret':1,'wall_s':.01,'source':{},'tools':{},'artifacts':{},
         'details':{'model':{'coverage_types':['line'],'probes':False}}}
    database=tmp_path/'coverage.json';database.write_text(json.dumps({'schema':'rvw.coverage/1','point_universe':'fixture',
        'tests':{'tiny':{'run':old}},'points':[{'id':'point','count':1,'tests':{'tiny':1}}]}))
    monkeypatch.setattr(module,'load_config',lambda **kw:SimpleNamespace(name='fixture',configs=['test'],adapter=['unused'],lock=None))
    calls=[]
    def expired(command,**kw):
        calls.append(kw['timeout'])
        manifest=command[command.index('--manifest')+1]
        for line in open(manifest):
            job=json.loads(line);out=__import__('pathlib').Path(job['out']);out.mkdir()
            (out/'result.json').write_text(json.dumps(old|{'status':native_status,'fail_code':1 if native_status=='fail' else None,'options':{'coverage':True,'probes':False}}))
        return SimpleNamespace(timed_out=timed_out,returncode=-15 if timed_out else 1)
    monkeypatch.setattr(module,'run_group',expired)
    result=module.execute_json(database,2,run=True,project='fixture',work_dir=tmp_path/'run')
    assert calls==[2]
    assert result['status']==expected and result['execution']['observations'][0]['status']==native_status
    assert result['new_execution_coverage_credit'] is False
