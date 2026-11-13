import shutil
import sqlite3
from pathlib import Path
import pytest
from rvw.common.capture import Capture
from rvw.formal.database_autocheck import enum_states, populate
from rvw.formal.autocheck import expand
from rvw.formal.apps import generate


def test_complete_sparse_enum_and_unknown_encoding():
    assert enum_states('State@custom[4]{idle=0,busy=3,done=a}') == [0, 3, 10]
    assert enum_states('State@seq{h:abc}') is None
    assert enum_states('$incomplete:enum') is None


def test_real_database_port_and_enum_inventory(gcd_db, tmp_path):
    path = tmp_path / 'enum.db'
    shutil.copyfile(gcd_db, path)
    db = sqlite3.connect(path)
    db.execute("UPDATE signals SET type='State@custom[32]{idle=0,busy=1,done=a}' WHERE name='io_result'")
    db.commit()
    db.close()
    capture = Capture(tmp_path / 'capture')
    plan, evidence = populate({'schema': 'rvw.autocheck/1', 'top': 'GCD', 'clock': 'clk', 'reset': 'reset'}, path, capture)
    assert plan['ports']['clk']['direction'] == 'input'
    assert plan['ports']['io_result']['direction'] == 'output'
    assert plan['fsms'][0]['states'] == [0, 1, 10]
    assert len(plan['fsms'][0]['transitions']) == 9
    expanded = expand(plan)
    for prop in expanded['properties']:
        assert 'assert (' in generate(expanded, prop)
    assert capture.record()['files']
    assert evidence['component'] == ''


def test_database_rejects_conflicting_ports(gcd_db, tmp_path):
    with pytest.raises(ValueError, match='ports differ'):
        populate({'top': 'GCD', 'ports': {'clk': {'direction': 'output', 'width': 1}}}, gcd_db, Capture(tmp_path / 'capture'))


def test_database_arithmetic_and_memory_address_candidates(gcd_db, tmp_path):
    path = tmp_path / 'operations.db'
    shutil.copyfile(gcd_db, path)
    db = sqlite3.connect(path)
    db.execute("UPDATE assignments SET source='io_a + io_b', cond_id=NULL, target_id=4 WHERE id=(SELECT min(id) FROM assignments)")
    db.execute("INSERT INTO memories(id,signal_id,component_id,name,path,width,depth) VALUES(900,1,1,'small','small',32,3)")
    db.execute("INSERT INTO mem_ports(id,memory_id,component_id,kind,address,enable) VALUES(900,900,1,'read','io_a','io_loadValues')")
    db.commit()
    db.close()
    plan, _ = populate({'schema': 'rvw.autocheck/1', 'top': 'GCD', 'clock': 'clk', 'reset': 'reset'}, path, Capture(tmp_path / 'capture'))
    kinds = {p['kind'] for p in plan['contracts']}
    assert {'arithmetic_overflow', 'array_bound'} <= kinds
    expanded = expand(plan, kinds=['array_bound', 'arithmetic_overflow'])
    for prop in expanded['properties']:
        assert 'assert (' in generate(expanded, prop)


def test_generated_source_lines_are_from_database(gcd_db, tmp_path):
    plan, _ = populate({'schema': 'rvw.autocheck/1', 'top': 'GCD', 'clock': 'clk', 'reset': 'reset'}, gcd_db, Capture(tmp_path / 'capture'))
    prop = next(p for p in expand(plan)['properties'] if p.get('signal') == 'io_result')
    assert prop['source']['line'] == 11 and prop['source']['file'].endswith('Gcd.scala')
    assert prop['module'] == 'GCD' and prop['origin'] == 'generated'


def test_internal_enum_exposure_plan(gcd_db, tmp_path):
    path = tmp_path/'internal.db'
    shutil.copyfile(gcd_db, path)
    db = sqlite3.connect(path)
    db.execute("UPDATE signals SET type='State@seq[32]{idle=0,busy=1}', direction=NULL WHERE name='io_result'")
    db.commit(); db.close()
    plan, evidence = populate({'schema': 'rvw.autocheck/1', 'top': 'GCD'}, path, Capture(tmp_path/'capture'))
    assert plan['internal_ports']['io_result'] == 32
    assert plan['fsms'][0]['signal'] == 'io_result'
    assert any(r['role'] == 'fsm' for r in evidence['roles'])


def test_typed_output_stream_contract(gcd_db, tmp_path):
    from types import SimpleNamespace
    from rvw.formal.role_discovery import discover
    class DB:
        def q(self, sql, args):
            if 'FROM bundles' in sql:
                return [(1, 'io_pop', 'spinal.lib.Stream')]
            if 'class_name FROM components' in sql:
                return [('Top',)]
            return []
    signals = [SimpleNamespace(id=i, path='io_pop.'+n, name='io_pop_'+n, width=w, type='Bits', kind='wire')
               for i,(n,w) in enumerate([('valid',1),('ready',1),('payload',8)])]
    ports = {s.name: {'direction': 'input' if s.name.endswith('ready') else 'output', 'width': s.width} for s in signals}
    roles, contracts = discover(DB(),1,signals,ports)
    assert roles[0]['role'] == 'handshake'
    assert contracts[0]['kind'] == 'stream_stability'
    plan = {'top':'Top','clock':'clk','reset':'reset','ports':dict(ports,clk={'direction':'input','width':1},reset={'direction':'input','width':1})}
    assert 'rvwa_stalled' in generate(plan,contracts[0])
