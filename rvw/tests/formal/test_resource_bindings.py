import pytest
from rvw.formal.micro_checks import generate,PORTS


def rule(kind,**params):
    return dict(id='unit',kind=kind,width=3,entries=4,ports={p:'project_'+p for p in ('clk','reset',*PORTS[kind])},**params)


@pytest.mark.parametrize('kind',['allocation_pool','freelist_conservation','rob','credit','freelist','cam_match','counter_bounds'])
def test_named_project_resource_binding(tmp_path,kind):
    result=generate(dict(schema='rvw.micro-checks/1',top='Top',rules=[rule(kind)]),tmp_path/'out')
    assert result['complete'] is True
    assert '.clk(project_clk)' in (tmp_path/'out/binds.sv').read_text()
    assert 'module rvw_rule_unit' in (tmp_path/'out/monitors.sv').read_text()


def test_nonempty_reset_ownership_and_reserved_tags_are_explicit(tmp_path):
    result=generate(dict(schema='rvw.micro-checks/1',top='Top',rules=[rule('freelist_conservation',initial_live=1,usable=7)]),tmp_path/'out')
    assert result['rules'][0]['initial_live']==1 and result['rules'][0]['usable']==7
    assert ".INITIAL_LIVE(4'd1),.USABLE(4'd7)" in (tmp_path/'out/binds.sv').read_text()


@pytest.mark.parametrize('params',[dict(initial_live=16),dict(initial_live=8,usable=7),dict(usable=-1)])
def test_invalid_reset_ownership_does_not_bind(tmp_path,params):
    result=generate(dict(schema='rvw.micro-checks/1',top='Top',rules=[rule('freelist_conservation',**params)]),tmp_path/'out')
    assert result['status']=='no_checks' and not result['complete']
    assert 'subset' in result['rules'][0]['reason']
