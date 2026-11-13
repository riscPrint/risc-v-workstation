import hashlib
import json
import sqlite3
import pytest
from rvw.farm.observations import observe
from rvw.farm.selection import select
from rvw.results import SuiteResults, TestEntry, save_results

pytestmark = pytest.mark.fast


def fixture(tmp_path):
    db=tmp_path/'design.db'
    with sqlite3.connect(db) as connection:
        connection.executescript("CREATE TABLE files(id,path); CREATE TABLE components(id,file_id); CREATE TABLE signals(id,path,component_id,file_id,pruned); CREATE TABLE edges(src,dst);")
        connection.execute("INSERT INTO files VALUES(1,'Unit.scala')")
        connection.execute('INSERT INTO components VALUES(1,1)')
        connection.executemany('INSERT INTO signals VALUES(?,?,?,?,0)',[(1,'active',1,1),(2,'idle',1,1)])
    root=tmp_path/'run';cell=root/'cell';cell.mkdir(parents=True)
    digest=hashlib.sha256(b'elf').hexdigest()
    save_results(SuiteResults('run','isa','generic','small','2026-11-13',tests=[
        TestEntry('test','pass',seed=1,wall_s=.5,run='cell',extra={'elf_sha256':digest})]),root)
    (cell/'result.json').write_text(json.dumps(dict(schema='rvw.run/1',status='pass',core='generic',config='small',seed=1,elf_sha256=digest,artifacts={'wave':'wave.vcd'})))
    (cell/'wave.vcd').write_text('''$timescale 1ns $end
$scope module TOP $end
$scope module Unit $end
$var wire 1 ! active $end
$var wire 1 " idle $end
$upscope $end
$upscope $end
$enddefinitions $end
#0
0!
0"
#5
1!
''')
    return db,root,cell


def test_real_value_changes_map_exact_database_names(tmp_path):
    db,root,_=fixture(tmp_path)
    report=observe(db,root,'TOP.Unit')
    assert report['tests'][0]['signals']==['active']
    assert report['tests'][0]['mapped_signals']==2
    assert report['database_sha256']==hashlib.sha256(db.read_bytes()).hexdigest()
    assert report['issues']==[]


def test_unknown_mapping_stays_mandatory(tmp_path):
    db,root,_=fixture(tmp_path)
    report=observe(db,root,'wrong.prefix')
    assert 'signals' not in report['tests'][0]
    planned=select(db,['Unit.scala'],report,.1)
    assert planned['selected'][0]['id']=='test'
    assert planned['over_budget']


def test_changed_c1_identity_is_refused(tmp_path):
    db,root,cell=fixture(tmp_path)
    p=cell/'result.json';r=json.loads(p.read_text());r['seed']=2;p.write_text(json.dumps(r))
    with pytest.raises(ValueError,match='identity'):
        observe(db,root,'TOP.Unit')


def test_coverage_required_tests_cannot_be_omitted_for_time(tmp_path):
    db,root,_=fixture(tmp_path)
    report=observe(db,root,'TOP.Unit')
    report['tests'][0]['signals']=[]
    report['coverage_selection']={'tests':['test'],'fallback_all':False}
    planned=select(db,['Unit.scala'],report,.1)
    assert [t['id'] for t in planned['selected']]==['test']
    assert planned['over_budget']
    report['coverage_selection']['tests']=['missing']
    with pytest.raises(ValueError,match='absent'):
        select(db,['Unit.scala'],report,.1)


def test_wave_aliases_retain_all_exact_database_paths(tmp_path):
    db,root,cell=fixture(tmp_path)
    with sqlite3.connect(db) as connection:
        connection.execute("INSERT INTO signals VALUES(3,'active_alias',1,1,0)")
    p=cell/'wave.vcd';s=p.read_text().replace('$var wire 1 ! active $end','$var wire 1 ! active $end\n$var wire 1 ! active_alias $end');p.write_text(s)
    report=observe(db,root,'TOP.Unit')
    assert report['tests'][0]['signals']==['active','active_alias']
    assert report['tests'][0]['mapped_signals']==3
    assert report['tests'][0]['mapped_codes']==2
