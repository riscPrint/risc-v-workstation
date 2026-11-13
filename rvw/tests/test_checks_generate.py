import json
import pytest
from rvw.checks.generate import generate


def project(tmp_path,spec):
    (tmp_path/'rvw.toml').write_text('[core]\nname="test"\n')
    (tmp_path/'checks.generate.json').write_text(json.dumps(dict(schema='rvw.check-generation/1',**spec)))
    return tmp_path/'rvw.toml'


def test_missing_kinds_cannot_pass(tmp_path):
    result=generate(project(tmp_path,{}),'out')
    assert result['status']=='no_checks'
    assert not result['complete']
    assert len(result['checks'])==6
    assert all(row['reason'] for row in result['checks'])
    with pytest.raises(FileExistsError): generate(tmp_path,'out')


def test_project_rules_and_missing_sources(tmp_path):
    p=project(tmp_path,dict(queues='rules.json',power='missing.json'))
    (tmp_path/'rules.json').write_text(json.dumps(dict(schema='rvw.micro-checks/1',top='Top',rules=[
      dict(id='grant',kind='mutex',entries=4,ports=dict(clk='clk',reset='reset',grants='io_grant'))])))
    result=generate(p,'out')
    assert result['status']=='generated'
    assert not result['complete']
    assert result['checks'][3]['instances'][0]['status']=='generated'
    assert result['checks'][4]['status']=='unsupported'


def test_invalid_project_is_an_error(tmp_path):
    (tmp_path/'rvw.toml').write_text('not valid TOML')
    with pytest.raises(ValueError): generate(tmp_path,'out')


def test_partial_bus_transactions_keep_overall_summary_incomplete(tmp_path,monkeypatch):
    from rvw.checks import bindings
    def bound(kind,entry,base,out):
        row=dict(status='generated',instances=[])
        if kind=='buses':
            row['instances']=[dict(path='io.bus',status='generated',coverage='channel_safety',
                unbound_checks=[dict(kind='axi_transactions',reason='burst transaction tracking requires LAST')])]
        return row
    monkeypatch.setattr(bindings,'generate',bound)
    spec={kind:{} for kind in ('streams','buses','csrs','queues','power','cdc')}
    result=generate(project(tmp_path,spec),'out')
    assert result['status']=='generated' and result['complete'] is False
    assert result['unbound']==[dict(kind='buses',instance='io.bus',check='axi_transactions',
        reason='burst transaction tracking requires LAST')]


def test_missing_kind_summary_has_direct_reasons(tmp_path):
    result=generate(project(tmp_path,{}),'out')
    assert {r['kind'] for r in result['unbound']}=={'streams','buses','csrs','queues','power','cdc'}
    assert all(r['reason']=='no project data supplied' for r in result['unbound'])


def test_cdc_keeps_unsupported_and_missing_bindings(tmp_path):
    report=dict(config='small',top='Top',backends=dict(structural=dict(cdc=dict(obligations=[
        dict(id='gray',kind='gray_code',width=2,bind=dict(module='Top',ports=dict(clk='clk',value='gray'))),
        dict(id='missing',kind='data_stable',width=8),
        dict(id='unknown',kind='unsupported',width=1)]))))
    (tmp_path/'lint.json').write_text(json.dumps(report))
    result=generate(project(tmp_path,dict(cdc=dict(report='lint.json'))),'out')
    row=next(r for r in result['checks'] if r['kind']=='cdc')
    assert row['status']=='generated'
    assert [r['instance'] for r in result['unbound'] if r['kind']=='cdc']==['missing','unknown']
    text=(tmp_path/'out/cdc/cdc_checks.sv').read_text()
    assert 'bind Top rvw_cdc_gray' in text
    assert 'rvw_missing' not in text and 'rvw_unknown' not in text
    assert not result['complete']


def test_cdc_refuses_report_without_obligations(tmp_path):
    (tmp_path/'lint.json').write_text('{}')
    result=generate(project(tmp_path,dict(cdc=dict(report='lint.json'))),'out')
    row=next(r for r in result['checks'] if r['kind']=='cdc')
    assert row['status']=='unsupported'
    assert 'obligations' in row['reason']
