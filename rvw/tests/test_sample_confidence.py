import json
import pytest
from rvw.sample.confidence import statement

pytestmark=pytest.mark.fast


def test_empirical_error_does_not_become_guarantee(tmp_path):
    identity=dict(platform='p',mapping='m',adapter_files={})
    report=dict(schema='rvw.sample-validation/1',status='reported',identity=identity,warmup=100,
                elf_sha256='e',rows=[dict(interval=1000,max_k=4,status='estimated',signed_error_percent=-2)])
    p=tmp_path/'validation.json';p.write_text(json.dumps(report))
    r=statement(p,identity,1000,4,100)
    assert r['max_observed_error_percent']==2
    assert 'no statistical confidence' in r['method']
    with pytest.raises(ValueError,match='warmup'):
        statement(p,identity,1000,4,0)
    with pytest.raises(ValueError,match='settings'):
        statement(p,identity,100,4,100)
    with pytest.raises(ValueError,match='differs'):
        statement(p,dict(identity,platform='other'),1000,4,100)
    report['status']='inconclusive';p.write_text(json.dumps(report))
    with pytest.raises(ValueError,match='completed'):
        statement(p,identity,1000,4,100)
