import pytest
from rvw.cov.mutation_regression import check_expected
from rvw.cov.core_mutation import KILLS

pytestmark=pytest.mark.fast


def observation(state=KILLS[1],killer='add'):
    return dict(mutant_set_sha256='abc',baseline={'state':'survived'},
                mutants=[dict(id='m1',state=state,first_killer=killer)])


def pins():
    return dict(schema='rvw.mutation-expectations/1',mutant_set_sha256='abc',
                mutants=[dict(id='m1',killer='add',outcome=KILLS[1])])


@pytest.mark.parametrize('state,killer,expected',[
    (KILLS[1],'add','pass'),('survived',None,'fail'),('invalid',None,'inconclusive'),
    ('timeout',None,'inconclusive'),(KILLS[1],'other','fail'),(KILLS[0],'add','fail'),
])
def test_killer_regression(state,killer,expected):
    assert check_expected(observation(state,killer),pins())['status']==expected


def test_missing_mutant_and_failed_baseline():
    result=observation();result['mutants']=[]
    assert check_expected(result,pins())['status']=='inconclusive'
    result=observation();result['baseline']['state']='invalid'
    assert check_expected(result,pins())['status']=='inconclusive'


def test_plan_change_refused():
    result=observation();result['mutant_set_sha256']='changed'
    with pytest.raises(ValueError,match='identity'):check_expected(result,pins())


from .test_core_mutation import campaign


def test_regression_reruns_adapter_protocol(campaign,tmp_path):
    import json
    from rvw.cov.core_mutation import run_campaign
    from rvw.cov.mutation_regression import execute
    result=run_campaign(campaign)
    killer=next(r for r in result['mutants'] if r['state'] in KILLS)
    expected=tmp_path/'expected.json'
    expected.write_text(json.dumps(dict(schema='rvw.mutation-expectations/1',
        mutant_set_sha256=result['mutant_set_sha256'],
        mutants=[dict(id=killer['id'],killer=killer['first_killer'],outcome=killer['state'])])))
    assert execute(campaign,expected)['status']=='pass'
    assert len((campaign/'build-count').read_text().splitlines())==6
    assert (campaign/'previous-results.json').exists()


def test_new_suite_plan_retains_mutant_pins(campaign,tmp_path):
    import json
    from rvw.cov.core_mutation import prepare,run_campaign
    first=run_campaign(campaign)
    (campaign.parent/'test.elf').write_text('changed test suite fixture')
    fresh=tmp_path/'new-suite'
    prepare(campaign.parent/'project.json',fresh)
    second=run_campaign(fresh)
    assert first['plan_sha256']!=second['plan_sha256']
    assert first['mutant_set_sha256']==second['mutant_set_sha256']
