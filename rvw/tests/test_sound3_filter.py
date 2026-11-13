from dataclasses import replace
import pytest
from rvw.regress.plan import gate
from test_regress_gate_clarity import rtl_core
from rvw.regress.source import describe

pytestmark = pytest.mark.fast

@pytest.mark.parametrize('filtered',[False,True])
def test_gate_records_test_selection(fake,tmp_path,filtered):
    runner,_ = rtl_core(fake,tmp_path)
    filters=['^rv64ui-p-add$'] if filtered else []
    opts=replace(runner.opts,include=filters)
    verdict=gate(
        runner.core,'quick',describe(fake.repo).rev,
        None,None,None,None,opts,None,None)['verdict']
    info=verdict.extra['gate']
    assert info['filter']==(filters or None)
    # The fixture tier contains add and sub. The filter selects only add.
    assert (info['selected_tests'],info['total_tests'])==(1 if filtered else 2, 2)
    assert verdict.verdict=='accept'
    assert verdict.extra.get('scope')==('filtered' if filtered else None)


def test_plan_refuses_filtered_accept(tmp_path):
    import json
    from rvw.regress.compare import compare
    from test_regress_commit_gate import _suite, COMMITTED
    from rvw.plan.model import VPlan
    verdict=compare([_suite(COMMITTED)],[_suite(COMMITTED)]).to_dict()
    verdict.update(scope='filtered',gate={'filter':['one']})
    (tmp_path/'verdict.json').write_text(json.dumps(verdict))
    path=tmp_path/'plan.json'
    path.write_text(json.dumps(dict(schema='rvw.vplan/1',requirements={'r':'require tier'},features=[
        dict(id='f',requirements=['r'],checks=[dict(path='verdict.json',kind='gate')])])))
    result=VPlan(path).status()
    assert result['verdict']=='inconclusive'
    assert 'filtered_gate' in result['features'][0]['holes'][0]['reason']


def test_farm_refuses_subset_input(tmp_path):
    from test_farm_gate_intake import fixture
    from rvw.farm.gate_intake import intake
    from rvw.results import save_results
    root,_,_,result=fixture(tmp_path)
    result.extra['filter']=['one']
    save_results(result,root)
    with pytest.raises(ValueError,match='filtered_gate'):
        intake(root)
