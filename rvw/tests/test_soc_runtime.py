import copy
import hashlib
import json
from pathlib import Path
import pytest
from rvw.soc.model import generate, load, dumps
from rvw.soc.capture import check_capture
from rvw.soc.importer import import_ipxact, NS
from rvw.cosim.platform import Platform

ROOT = Path(__file__).resolve().parents[2]

@pytest.mark.parametrize('core', ['boom', 'vexriscv'])
def test_source_platform_runtime(core, tmp_path):
    source = ROOT / 'examples' / core / 'soc.json'
    generate(source, tmp_path)
    a = Platform.load(core, source)
    b = Platform.load(core, tmp_path / 'platform.json')
    assert a.describe() == b.describe()

@pytest.fixture
def capture(tmp_path):
    source = ROOT / 'examples/vexriscv/soc.json'
    generate(source, tmp_path)
    digest = hashlib.sha256((tmp_path / 'sim-map.json').read_bytes()).hexdigest()
    identity = {'rtl_sha256':'abc', 'source':{'core_rev':'def'}, 'session_id':'123', 'elf_sha256':'456', 'seed':1}
    header = dict(schema='rvw.soc-capture/1', map_sha256=digest, identity=identity)
    rows = [header, dict(cycle='1', bus='ibus', address='0x80000000', size='4', write=False, selected='ram'), dict(event='end')]
    result = tmp_path / 'result.json'
    result.write_text(dumps(dict(identity, soc_map_sha256=digest, details={'simulation_session':{'id':'123'}})))
    path = tmp_path / 'soc-transactions.jsonl'
    path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    return source, path, result, rows

def test_capture_and_decoder_mutation(capture):
    source, path, result, rows = capture
    r = check_capture(source, path, result)
    assert r['transactions'] == 1 and r['status'] == 'inconclusive'
    rows[1]['selected'] = 'wrong'
    path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    assert check_capture(source, path, result)['status'] == 'mismatch'

@pytest.mark.parametrize('field', ['rtl_sha256', 'source', 'soc_map_sha256'])
def test_capture_identity_mutation(capture, field):
    source, path, result, _ = capture
    obj = json.loads(result.read_text()); obj.pop(field)
    result.write_text(dumps(obj))
    with pytest.raises(ValueError):
        check_capture(source, path, result)

def test_truncated_capture(capture):
    source, path, result, rows = capture
    path.write_text(''.join(json.dumps(r)+'\n' for r in rows[:-1]))
    r = check_capture(source, path, result)
    assert not r['complete'] and 'capture end' in r['gaps']

@pytest.fixture
def ipxact(tmp_path):
    source = tmp_path / 'map.xml'
    source.write_text(f'''<memoryMap xmlns="{NS}"><name>timer</name><addressUnitBits>8</addressUnitBits>
<addressBlock><name>clint</name><baseAddress>0x02000000</baseAddress><range>0x10000</range><width>64</width><usage>register</usage>
<register><name>msip</name><addressOffset>0</addressOffset><size>32</size><access>read-write</access><field><name>value</name><bitOffset>0</bitOffset><resets><reset><value>0</value><mask>0xffffffff</mask></reset></resets><bitWidth>32</bitWidth></field></register>
<register><name>mtimecmp</name><addressOffset>0x4000</addressOffset><size>64</size><access>read-write</access><field><name>value</name><bitOffset>0</bitOffset><bitWidth>64</bitWidth></field></register>
</addressBlock></memoryMap>''')
    return source

def test_import_registers(ipxact, tmp_path):
    out = tmp_path / 'soc.json'
    assert import_ipxact(ipxact, ROOT / 'examples/boom/soc.json', out) == ['clint']
    regs = load(out)['regions'][1]['registers']
    assert regs[0]['reset'] == 0 and regs[1]['offset'] == 0x4000
    assert regs[1]['reset'] is None

@pytest.mark.parametrize('old,new', [('0xffffffff','0xff'), ('<name>msip</name>', '<name/>'), ('<size>32</size>', '<size>32</size><field/>'), ('<range>0x10000</range>', '<range>0x1000</range>'), ('<bitOffset>0', '<bitOffset>1'), ('<addressUnitBits>8', '<addressUnitBits>16'), ('<access>read-write</access>', '<access>read-writeOnce</access>')])
def test_import_refuses_loss(ipxact, tmp_path, old, new):
    ipxact.write_text(ipxact.read_text().replace(old,new))
    out = tmp_path / 'soc.json'
    with pytest.raises(ValueError):
        import_ipxact(ipxact, ROOT / 'examples/boom/soc.json', out)
    assert not out.exists()

def test_large_register_reset_remains_exact(tmp_path):
    source = ROOT / 'examples/boom/soc.json'
    generate(source, tmp_path)
    sim = json.loads((tmp_path / 'sim-map.json').read_text())
    assert sim['regions'][1]['registers'][1]['reset'] == '0xffffffffffffffff'

@pytest.mark.parametrize('address,selected', [('0x81000000', 'ram'), ('0x80000000', None), ('0x80ffffff', 'ram')])
def test_capture_bounds_mutations(capture, address, selected):
    source, path, result, rows = capture
    rows[1].update(address=address, selected=selected)
    path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    assert check_capture(source, path, result)['status'] == 'mismatch'

@pytest.mark.parametrize('field', ['session_id', 'elf_sha256', 'seed'])
def test_capture_run_identity_mutation(capture, field):
    source, path, result, rows = capture
    rows[0]['identity'].pop(field)
    path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    with pytest.raises(ValueError):
        check_capture(source, path, result)


def test_import_side_effects(ipxact, tmp_path):
    ipxact.write_text(ipxact.read_text().replace('<bitWidth>32</bitWidth>', '<bitWidth>32</bitWidth><modifiedWriteValue>oneToClear</modifiedWriteValue><readAction>clear</readAction>'))
    out = tmp_path / 'soc.json'
    import_ipxact(ipxact, ROOT / 'examples/boom/soc.json', out)
    reg = load(out)['regions'][1]['registers'][0]
    assert reg['write_action'] == 'one_to_clear' and reg['read_action'] == 'clear'

def test_import_cli_rejects_bad_xml(tmp_path, capsys):
    from argparse import Namespace
    from rvw.soc.cli import run
    source = tmp_path / 'invalid.xml'
    source.write_text('<memoryMap')
    code = run(Namespace(soc_command='import-ipxact', source=source, template=ROOT / 'examples/boom/soc.json', out=tmp_path/'out.json', json=True))
    assert code == 2
    assert json.loads(capsys.readouterr().out)['status'] == 'error'
