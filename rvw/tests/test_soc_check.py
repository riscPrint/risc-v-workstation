import json
import sqlite3
from pathlib import Path

import pytest

from rvw.cli import main
from rvw.soc.check import check

ROOT = Path(__file__).resolve().parents[2]
MAP = ROOT / 'examples/vexriscv/soc.json'


@pytest.fixture
def setup(tmp_path):
    db = tmp_path / 'design.db'
    c = sqlite3.connect(db)
    c.executescript('''CREATE TABLE meta(key,value);
      INSERT INTO meta VALUES('schema','rvw.designdb/20');
      CREATE TABLE signals(id,path,width);
      INSERT INTO signals VALUES(1,'bus_address',32),(2,'ram_hit',1);
      CREATE TABLE assignments(target_id,kind,key,seq,cond_id,range);''')
    c.execute('INSERT INTO assignments VALUES(?,?,?,?,?,?)', (2,'data',' := decode(80000000,ff000000)',0,None,None))
    c.commit()
    c.close()
    spec = dict(schema='rvw.soc-bindings/1', signals=[dict(path='bus_address',width='address_bits')],
                decoders=[dict(region='ram',path='ram_hit',key_template=' := decode({base},{mask})')],
                bridges=[dict(name='ram_bridge',region='ram',local_base=0,data_bytes=4)])
    binding = tmp_path / 'bindings.json'
    binding.write_text(json.dumps(spec))
    return db,binding


def test_exact_structure_stays_inconclusive(setup):
    db,binding = setup
    result = check(MAP,binding,db)
    assert result['status'] == 'inconclusive'
    assert all(c['status'] == 'consistent' for c in result['checks'])
    assert 'sampled transactions' in result['gaps']


@pytest.mark.parametrize('mutation', ["UPDATE signals SET width=64 WHERE id=1", "UPDATE assignments SET key=' := decode(80000000,fe000000)'"])
def test_bad_width_or_decode(setup, mutation):
    db,binding = setup
    with sqlite3.connect(db) as c:
        c.execute(mutation)
    assert check(MAP,binding,db)['status'] == 'mismatch'


def test_missing_and_ambiguous_evidence(setup):
    db,binding = setup
    with sqlite3.connect(db) as c:
        c.execute('DELETE FROM signals WHERE id=1')
        c.execute('INSERT INTO assignments SELECT * FROM assignments')
    result = check(MAP,binding,db)
    assert result['status'] == 'inconclusive'
    assert all(c['status'] == 'unavailable' for c in result['checks'])


@pytest.mark.parametrize('sw,bus,size,status', [('0x80000000',0,4,'inconclusive'), ('0x80000000',4,4,'mismatch'), ('0x81000000','0x1000000',4,'mismatch'), ('0x80000003',3,2,'mismatch')])
def test_transactions(setup,tmp_path,sw,bus,size,status):
    db,binding = setup
    trace = tmp_path / 'tx.jsonl'
    trace.write_text(json.dumps(dict(bridge='ram_bridge',software_address=sw,bus_address=bus,size=size))+'\n')
    result = check(MAP,binding,db,trace)
    assert result['status'] == status
    assert result['transactions'] == 1


def test_cli(setup,capsys):
    db,binding = setup
    assert main(['soc','check',str(MAP),'--bindings',str(binding),'--db',str(db),'--json']) == 3
    assert json.loads(capsys.readouterr().out)['status'] == 'inconclusive'
    assert main(['soc','check',str(MAP),'--bindings',str(binding),'--db',str(db)+'missing','--json']) == 2
    assert json.loads(capsys.readouterr().out)['status'] == 'error'


@pytest.mark.parametrize('mutation', ["UPDATE assignments SET cond_id=1", "UPDATE assignments SET range='(0)'", "UPDATE assignments SET key='h:unknown'"])
def test_partial_opaque_decoder_is_unavailable(setup, mutation):
    db,binding = setup
    with sqlite3.connect(db) as c:
        c.execute(mutation)
    result = check(MAP,binding,db)
    assert result['status'] == 'inconclusive'
    assert result['checks'][1]['status'] == 'unavailable'


def test_paired_beats_check_and_negative(setup, tmp_path):
    db, binding = setup
    spec = json.loads(binding.read_text())
    spec['bridges'][0].update(data_bytes=2, byteorder='big')
    binding.write_text(json.dumps(spec))
    trace = tmp_path / 'tx.jsonl'
    t = dict(bridge='ram_bridge', software_address='0x80000000', bus_address=0, size=4,
             write=False, data=0x12345678, error=False,
             beats=[dict(address=0, data=0x7856, mask=3, error=False, write=False),
                    dict(address=2, data=0x3412, mask=3, error=False, write=False)])
    trace.write_text(json.dumps(t) + '\n')
    result = check(MAP, binding, db, trace)
    assert result['status'] == 'inconclusive'
    assert all(c['status'] == 'consistent' for c in result['checks'])
    t['beats'][1]['data'] ^= 1
    trace.write_text(json.dumps(t) + '\n')
    assert check(MAP, binding, db, trace)['status'] == 'mismatch'
