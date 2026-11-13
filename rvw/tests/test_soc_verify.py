import hashlib
import json
import sys
from pathlib import Path

import pytest
from rvw.soc.verify import verify, table
from rvw.checks.soc_registers import RegisterEffects

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]
MAP = ROOT/'SpinalSoc/examples/vex/soc.json'


def test_missing_consumers_are_not_passes(tmp_path):
    result = verify(MAP, tmp_path/'out')
    assert result['status'] == 'inconclusive'
    assert len(result['checks']) == 7
    assert all(not r['ran'] for r in result['checks'])
    assert 'decode | yes | no | inconclusive' in table(result)


def test_zero_exit_without_evidence_is_not_pass(tmp_path):
    manifest = tmp_path/'verify.json'
    manifest.write_text(json.dumps(dict(schema='rvw.soc-verify/1', checks={
        'protocol':dict(command=[sys.executable,'-c','pass'])})))
    result = verify(MAP, tmp_path/'out', manifest)
    row = result['checks'][0]
    assert row['ran'] and row['returncode'] == 0
    assert row['result'] == 'inconclusive'


@pytest.mark.parametrize('status,checks,hash_ok,expected', [
    ('pass',1,True,'pass'), ('pass',0,True,'inconclusive'),
    ('pass',1,False,'inconclusive'), ('fail',1,True,'fail')])
def test_consumer_evidence(tmp_path, status, checks, hash_ok, expected):
    script = tmp_path/'consumer.py'
    script.write_text('''import hashlib,json,sys
from pathlib import Path
p=Path(sys.argv[1]); m=Path(sys.argv[2])
e=dict(schema='rvw.soc-verify-evidence/1',kind='protocol',status=sys.argv[3],checks=int(sys.argv[4]),
map_sha256=hashlib.sha256(m.read_bytes()).hexdigest() if sys.argv[5]=='True' else 'stale')
p.write_text(json.dumps(e))
''')
    manifest = tmp_path/'verify.json'
    manifest.write_text(json.dumps(dict(schema='rvw.soc-verify/1',checks={
        'protocol':dict(command=[sys.executable,str(script),'{result}','{map}',status,str(checks),str(hash_ok)])})))
    result = verify(MAP,tmp_path/'out',manifest)
    assert result['checks'][0]['result'] == expected
    assert result['status'] != 'pass'  # Other kinds remain missing.


def effects_map(tmp_path):
    data = json.loads(MAP.read_text())
    regs = data['regions'][1]['registers']
    regs[:] = [dict(name='effects',offset=0,width=32,access='rw',reset=255,
                    read_action='clear',write_action='one_to_clear')]
    data['interrupts'] = []
    path = tmp_path/'map.json'
    path.write_text(json.dumps(data))
    return path


def test_side_effect_order_and_corrupted_response(tmp_path):
    monitor = RegisterEffects(effects_map(tmp_path))
    address = 0x10000000
    monitor.observe(address, True, 3)
    monitor.observe(address, False, 0, 252)
    monitor.observe(address, False, 0, 0)
    assert monitor.finish()['checks'] == 2
    monitor.reset()
    with pytest.raises(AssertionError, match='SOC_REGISTER_DATA'):
        monitor.observe(address, False, 0, 0)


def test_unknown_reset_never_learns_from_dut(tmp_path):
    path = effects_map(tmp_path)
    data = json.loads(path.read_text())
    data['regions'][1]['registers'][0].update(reset=None,read_action='none',write_action='normal')
    path.write_text(json.dumps(data))
    monitor = RegisterEffects(path)
    monitor.observe(0x10000000, False, 0, 77)
    assert monitor.finish()['checks'] == 0
    monitor.observe(0x10000000, True, 12)
    with pytest.raises(AssertionError, match='SOC_REGISTER_DATA'):
        monitor.observe(0x10000000, False, 0, 77)


def test_apb_capture_checks_actual_response(tmp_path):
    from rvw.soc.apb_capture import check
    source = effects_map(tmp_path)
    capture = tmp_path/'apb.jsonl'
    header = dict(schema='rvw.soc-apb-samples/1',observation='rtl_peripheral_ports')
    setup = dict(bus='uart',cycle=1,psel=1,penable=0,paddr=0,pwrite=0,pwdata=0,
                 pready=1,prdata=255,pslverr=0)
    access = dict(setup,cycle=2,penable=1)
    def write(response):
        capture.write_text('\n'.join(json.dumps(r) for r in [header,setup,dict(access,prdata=response),{'end':True}])+'\n')
    write(255)
    assert check(source,capture)['registers']['checks'] == 1
    write(17)
    with pytest.raises(AssertionError, match='SOC_REGISTER_DATA'):
        check(source,capture)


def test_byte_mask_does_not_clear_unselected_bits(tmp_path):
    monitor = RegisterEffects(effects_map(tmp_path))
    monitor.observe(0x10000000, True, 255, strobe=0)
    monitor.observe(0x10000000, False, 0, 255)
    assert monitor.finish()['checks'] == 1


def test_register_environment_keeps_unknown_reads_unchecked(tmp_path):
    from rvw.uvm.soc import SocRegisterEnvironment
    from rvw.vip.apb import Pins
    env = SocRegisterEnvironment(effects_map(tmp_path))
    env.buses['uart'].sample(Pins(psel=1,penable=0,paddr=0))
    env.buses['uart'].sample(Pins(psel=1,penable=1,paddr=0,prdata=255))
    report = env.finish()
    assert report['checks'] == 1
    assert report['transfers']['uart'] == 1
