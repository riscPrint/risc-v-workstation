from hashlib import sha256
import json
import pytest
from rvw.cov.block_evidence import check,source_id


def setup(tmp_path):
    source=tmp_path/'block.v';source.write_text('module block; endmodule\n')
    digest=sha256(source.read_bytes()).hexdigest()
    receipt={'source_id':source_id({'block.v':digest}),'parameters':{'WIDTH':8},'assumptions':{'reset':'sync-active-high'}}
    run=tmp_path/'result.json';run.write_text(json.dumps({'schema':'rvw.run/1','status':'pass',
        'details':{'block_evidence':receipt}}))
    evidence={'schema':'rvw.block-evidence/1','sources':{'block.v':{'path':'block.v','sha256':digest}},
        'configurations':[{'parameters':receipt['parameters'],'assumptions':receipt['assumptions'],
                           'runs':[{'path':'result.json','sha256':sha256(run.read_bytes()).hexdigest()}]}]}
    integration={'schema':'rvw.block-integration/1','sources':{'block.v':'block.v'},
                 'parameters':{'WIDTH':8},'environment':{'reset':'sync-active-high'}}
    a=tmp_path/'evidence.json';b=tmp_path/'integration.json'
    a.write_text(json.dumps(evidence));b.write_text(json.dumps(integration))
    return a,b


def test_exact_tested_configuration_transfers_only_block_evidence(tmp_path):
    a,b=setup(tmp_path);result=check(a,b)
    assert result['status']=='eligible_for_reuse' and result['holes']==[]
    assert result['new_wiring_covered'] is False


@pytest.mark.parametrize('field,value',[('parameters',{'WIDTH':16}),('environment',{}),('environment',{'reset':'async'})])
def test_changed_parameters_and_missing_assumptions_refuse(tmp_path,field,value):
    a,b=setup(tmp_path);data=json.loads(b.read_text());data[field]=value;b.write_text(json.dumps(data))
    assert check(a,b)['status']=='incompatible'


def test_changed_source_and_changed_record_refuse(tmp_path):
    a,b=setup(tmp_path);(tmp_path/'block.v').write_text('changed')
    assert check(a,b)['status']=='incompatible'
    a,b=setup(tmp_path);(tmp_path/'result.json').write_text('{}')
    assert check(a,b)['status']=='inconclusive'


def test_missing_receipt_and_inconclusive_c1_never_transfer(tmp_path):
    a,b=setup(tmp_path);run=tmp_path/'result.json'
    for contents in ({'schema':'rvw.run/1','status':'pass'}, {'schema':'rvw.run/1','status':'pass','inconclusive':'pending attribution'}):
        run.write_text(json.dumps(contents));data=json.loads(a.read_text())
        data['configurations'][0]['runs'][0]['sha256']=sha256(run.read_bytes()).hexdigest();a.write_text(json.dumps(data))
        assert check(a,b)['status']=='inconclusive'


def test_cli_mcp_api_parity(tmp_path):
    import subprocess,sys
    from rvw.cov.block_evidence import execute_json
    a,b=setup(tmp_path)
    ran=subprocess.run([sys.executable,'-m','rvw','cov','block-check','--evidence',str(a),'--integration',str(b),'--json'],
                       capture_output=True,text=True)
    assert ran.returncode==0,ran.stderr
    cli=json.loads(ran.stdout);api=execute_json(evidence=a,integration=b)
    assert cli['status']==api['status']=='eligible_for_reuse'
    assert cli['source_id']==api['source_id']
    assert cli['new_wiring_covered'] is False
