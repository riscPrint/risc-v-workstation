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
    assert len(result['checks'])==5
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
