import json
from copy import deepcopy
import pytest
from rvw.verification_plan.model import generate, check_vectors
from rvw.results import load_results


def obligation():
    return {'id':'xadd','kind':'extension','operand_bins':{'rs1':[0,1,0xffffffff],'rs2':[0,1]},
            'exceptions':['illegal_when_disabled'],
            'dependencies':['read_after_write','write_after_write'],
            'reference_vectors':[{'id':'one','inputs':{'rs1':1,'rs2':2},'expected':3,'author':'independent-model'}],
            'mutants':[{'id':'substitution','vector':'one','observed':-1,'author':'manual-subtraction-fault'}]}


def declaration(tmp_path, ob=None, **extra):
    obj = {'schema':'rvw.verification-obligations/1','specifications':{'unprivileged':'20240411'},'obligations':[ob or obligation()]}
    obj.update(extra)
    p = tmp_path / 'declaration.json'
    p.write_text(json.dumps(obj))
    return p


def test_generate_bins_and_dependencies(tmp_path):
    report = generate(declaration(tmp_path), tmp_path / 'plan.json')
    kinds = [c['kind'] for c in report['cases']]
    assert kinds.count('operand') == 6
    assert kinds.count('dependency') == 2
    assert kinds.count('exception') == kinds.count('reference') == kinds.count('mutant') == 1
    assert all(c['status'] == 'not_run' for c in report['cases'])
    assert report['status'] == 'generated'
    assert len(set(c['id'] for c in report['cases'])) == 11


def test_envcfg_matrix_is_versioned(tmp_path):
    ob = obligation()
    ob.update(kind='envcfg',csr='henvcfg',field='PBMTE',legal_writes=[0,1],contexts=['HS','VS'],
              transitions=['HS-to-VS','VS-to-HS'],enabled='PBMT applies',disabled='reserved PTE faults')
    report = generate(declaration(tmp_path,ob,specifications={'privileged':'20240411','hypervisor':'1.0'}),tmp_path/'plan.json')
    cases = [c for c in report['cases'] if c['kind']=='envcfg']
    assert len(cases)==16
    assert {c['expected_behavior'] for c in cases} == {'PBMT applies','reserved PTE faults'}
    assert report['specifications']['hypervisor']=='1.0'


@pytest.mark.parametrize('key',['reference_vectors','mutants','exceptions','dependencies','operand_bins'])
def test_incomplete_extension_refused(tmp_path,key):
    ob = obligation(); ob.pop(key)
    with pytest.raises(ValueError): generate(declaration(tmp_path,ob),tmp_path/'plan.json')


def test_no_default_specification(tmp_path):
    with pytest.raises(ValueError,match='versions'):
        generate(declaration(tmp_path,specifications={}),tmp_path/'plan.json')


def test_vacuous_mutant_refused(tmp_path):
    ob = obligation(); ob['mutants'][0]['observed']=3
    with pytest.raises(ValueError,match='must differ'):
        generate(declaration(tmp_path,ob),tmp_path/'plan.json')


@pytest.mark.parametrize('observed,status',[({},'error'),({'case-000009':3},'pass'),({'case-000009':-1},'fail')])
def test_vector_observations(tmp_path,observed,status):
    generate(declaration(tmp_path),tmp_path/'plan.json')
    (tmp_path/'observations.json').write_text(json.dumps(observed))
    report = check_vectors(tmp_path/'plan.json',tmp_path/'observations.json',tmp_path/'results.json')
    assert report['tests'][0]['status']==status
    assert len(load_results(tmp_path/'results.json').tests)==1


def test_plan_does_not_overwrite(tmp_path):
    p = declaration(tmp_path)
    generate(p,tmp_path/'plan.json')
    with pytest.raises(FileExistsError): generate(p,tmp_path/'plan.json')
