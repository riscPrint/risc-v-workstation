import json
import pytest
from rvw.soc.verification_bindings import files
pytestmark = pytest.mark.fast


def test_composed_consumers_keep_register_and_domain_bindings():
    model = dict(regions=[dict(name='timer',registers=[dict(name='control',access='rw',offset=0)])],interrupts=[])
    spec = dict(devices={'timer':dict(type='project',domain='slow')})
    generated = files(model,spec,'../compose.json')
    verify = json.loads(generated['verify.json'])
    assert verify['checks']['registers']['write_read']==['timer.control']
    rows = json.loads(generated['connections.json'])['connection']
    assert dict(id='timer_clk',kind='required',source='slow_clk',destination='timer.clk') in rows
    assert verify['checks']['protocol']['composition']=='../compose.json'


def test_protocol_consumer_runs_bound_fabric_proof(tmp_path, monkeypatch):
    from rvw.soc import protocol_proof
    from rvw.soc.verify import verify
    from pathlib import Path
    source = Path(__file__).resolve().parents[2]/'SpinalSoc/examples/soc.json'
    cp = tmp_path/'cp.txt'; cp.write_text('classpath')
    manifest = tmp_path/'verify.json'
    manifest.write_text(json.dumps(dict(schema='rvw.soc-verify/1',checks={'protocol':dict(classpath_file='cp.txt')})))
    called=[]
    def prove(*args):
        called.append(args)
        return dict(status='pass',checks=12,scope='Bounded fabric only')
    monkeypatch.setattr(protocol_proof,'prove',prove)
    result = verify(source,tmp_path/'out',manifest)
    row = result['checks'][0]
    assert called and row['ran'] and row['result']=='pass'
    assert row['scope']=='Bounded fabric only'
    assert result['status']=='inconclusive'
