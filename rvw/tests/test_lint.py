import json
import sqlite3
from pathlib import Path
import pytest
from rvw.cli import main
from rvw.lint import native, structural
from rvw.lint.cli import report
from rvw.query.db import run_on


def fixture_db(tmp_path, mode='unsafe', width=1):
    # The exact current extractor DDL; fixture rows model register-boundary designs.
    import re
    schema = Path(__file__).parents[2] / 'SpinalDB/spinaldb/src/main/scala/spinaldb/Schema.scala'
    ddl = re.findall(r'"""(CREATE TABLE.*?)"""|"(CREATE TABLE[^"\n]*)"', schema.read_text(), re.S)
    p = tmp_path / 'reference.db'
    c = sqlite3.connect(p)
    for a, b in ddl:
        c.execute(re.sub(r'\n\s*\|', '\n', a or b))
    c.execute("INSERT INTO meta VALUES('schema','rvw.designdb/20')")
    c.execute("INSERT INTO files VALUES(1,'Reference.scala')")
    c.execute("INSERT INTO components(id,path,name,depth) VALUES(1,'','Reference',0)")
    for i, clk in [(1, 'a'), (2, 'b')]:
        c.execute('INSERT INTO clock_domains(id,clock,clock_key,clock_edge,reset_kind) VALUES(?,?,?,?,?)',
                  (i, clk, clk + ':Bool', 'RISING', 'BOOT'))
    for i in (1, 2, 3):
        domain = 1 if i == 1 or mode == 'same' else 2
        c.execute('INSERT INTO signals(id,component_id,name,path,kind,width,clock_domain_id,file_id,line) VALUES(?,?,?,?,?,?,?,?,?)',
                  (i, 1, f'r{i}', f'r{i}', 'reg', width, domain, 1, i))
    c.execute("INSERT INTO edges VALUES(1,2,'data')")
    if mode == 'sync':
        c.execute("INSERT INTO edges VALUES(2,3,'data')")
    c.commit(); c.close()
    return p


@pytest.mark.parametrize('mode,width,rule', [('unsafe',1,'cdc.unsynchronized'), ('unsafe',8,'cdc.multi_bit'),
                                            ('sync',1,'cdc.sync_candidate'), ('same',8,None)])
def test_reference_paths(tmp_path, mode, width, rule):
    r = run_on(fixture_db(tmp_path, mode, width), structural.analyze)
    assert r['status'] == 'inconclusive'
    assert [f['rule'] for f in r['findings']] == ([rule] if rule else [])
    assert all(x['status'] == 'not_run' for x in r['rules'])


def settings(tmp_path, db):
    p = tmp_path / 'lint.json'
    p.write_text(json.dumps(dict(schema='rvw.lint-settings/1', config='reference', top='Reference',
                                db=str(db), backends=['structural'])))
    return p


def test_exact_waiver_retains_finding_and_unused(tmp_path):
    p = settings(tmp_path, fixture_db(tmp_path))
    cfg = json.loads(p.read_text())
    cfg['waivers'] = [dict(rule='cdc.unsynchronized', endpoint=e, reason='Test fault.', config='reference') for e in ['r2','missing']]
    p.write_text(json.dumps(cfg))
    r = report(p)
    assert r['status'] == 'inconclusive'
    assert [w['matches'] for w in r['waivers']] == [1,0]
    assert r['backends']['structural']['findings'][0]['disposition'] == 'waived'
    cfg['waivers'][0]['config'] = 'other'; p.write_text(json.dumps(cfg))
    with pytest.raises(ValueError, match='waiver'):
        report(p)


def test_native_adapters():
    v = native.parse('verilator', '%Warning-MULTIDRIVEN: /a.v:3:9: Multiple drivers\nunknown text')
    assert v[0]['rule'] == 'verilator.MULTIDRIVEN'
    assert v[0]['endpoint'] == '/a.v:3:9'
    v = native.parse('verible', '/a.sv:2:3: Use always_comb [always-comb]')
    assert v[0]['rule'] == 'verible.always-comb'


def test_cli_and_missing_backend(tmp_path, capsys, monkeypatch):
    p = settings(tmp_path, fixture_db(tmp_path))
    assert main(['lint','--settings',str(p),'--json']) == 1
    assert json.loads(capsys.readouterr().out)['status'] == 'findings'
    monkeypatch.setattr(native.shutil, 'which', lambda _: None)
    assert native.run('verible', ['x.v'], 'X', 1)['status'] == 'not_run'


def test_native_timeout_and_unparsed_failure(monkeypatch):
    from rvw.common.proc import Result
    monkeypatch.setattr(native.shutil, 'which', lambda _: '/tool')
    monkeypatch.setattr(native, 'run_group', lambda *a, **k: Result(1, stdout='unknown diagnostic'))
    r = native.run('verible', ['x.sv'], 'X', 1)
    assert r['status'] == 'inconclusive' and r['raw_output'] == 'unknown diagnostic'
    monkeypatch.setattr(native, 'run_group', lambda *a, **k: Result(124, timed_out=True))
    assert native.run('verilator', ['x.v'], 'X', 1)['status'] == 'inconclusive'


def test_project_settings(tmp_path, capsys):
    p = settings(tmp_path, fixture_db(tmp_path,'same'))
    project = tmp_path / 'rvw.toml'
    project.write_text('[core]\nname="reference"\n[lint]\nsettings="lint.json"\n')
    assert main(['lint','--project',str(project),'--json']) == 3
    assert json.loads(capsys.readouterr().out)['backends']['structural']['clock_count'] == 1


def test_mcp_registration():
    from rvw.lint.mcp_tools import mcp_tools
    assert mcp_tools()[0].name == 'lint_report'


def test_unknown_domain_and_comb_path(tmp_path):
    p = fixture_db(tmp_path)
    with sqlite3.connect(p) as c:
        c.execute("UPDATE signals SET kind='wire' WHERE id=2")
        c.execute("INSERT INTO edges VALUES(2,3,'cond')")
    r = run_on(p, structural.analyze)
    assert r['findings'][0]['endpoint'] == 'r3'
    with sqlite3.connect(p) as c:
        c.execute('UPDATE clock_domains SET clock_key=NULL WHERE id=2')
    r = run_on(p, structural.analyze)
    assert r['findings'][0]['rule'] == 'cdc.unknown_domain'


def test_database_config_mismatch(tmp_path):
    db = fixture_db(tmp_path)
    p = settings(tmp_path, db)
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO meta VALUES('config','other')")
    with pytest.raises(ValueError, match='config'):
        report(p)


@pytest.mark.parametrize('independent', [False, True])
def test_reset_crossings_same_clock(tmp_path, independent):
    p = fixture_db(tmp_path)
    with sqlite3.connect(p) as c:
        c.execute("UPDATE clock_domains SET clock_key='clk:Bool', reset_kind='SYNC', reset='reset', reset_key='reset:Bool', reset_active_high='true'")
        if independent:
            c.execute("UPDATE clock_domains SET reset='other', reset_key='other:Bool' WHERE id=2")
    r = run_on(p, structural.analyze)
    assert len(r['reset_crossings']) == int(independent)
    assert [f['rule'] for f in r['findings']] == (['rdc.independent_reset'] if independent else [])
    assert all(t['status'] == 'unknown_control' for t in r['reset_trees'])


def test_async_reset_release_and_unknown(tmp_path):
    p = fixture_db(tmp_path, 'same')
    with sqlite3.connect(p) as c:
        c.execute("UPDATE clock_domains SET reset_kind='ASYNC',reset='r3',reset_key=NULL WHERE id=1")
    r = run_on(p, structural.analyze)
    assert {f['rule'] for f in r['findings']} == {'rdc.async_release_unproved','rdc.unknown_control'}
    assert r['reset_trees'][0]['nodes'] == ['r3']
    assert r['reset_trees'][0]['status'] == 'structural_cone'


@pytest.mark.parametrize('backend', ['verilator','verible'])
def test_native_reference_lint(backend):
    import shutil
    if not shutil.which('verilator' if backend == 'verilator' else 'verible-verilog-lint'):
        pytest.skip(f'{backend} is not installed')
    root = Path(__file__).parent / 'data/lint'
    clean = native.run(backend, [str(root / 'Clean.v')], 'Clean', 30)
    assert clean['status'] == 'completed'
    if backend == 'verilator':
        assert clean['findings'] == []
        fault = native.run(backend, [str(root / 'Fault.v')], 'Fault', 30)
        assert fault['status'] == 'completed'
        assert any('WIDTH' in f['rule'] for f in fault['findings'])


def test_malformed_backend_is_input_error(tmp_path, capsys):
    p = settings(tmp_path, fixture_db(tmp_path))
    cfg = json.loads(p.read_text()); cfg['backends'] = [{}]
    p.write_text(json.dumps(cfg))
    assert main(['lint', '--settings', str(p), '--json']) == 2
    assert json.loads(capsys.readouterr().out)['status'] == 'error'


def test_no_reset_has_no_reset_kind(tmp_path):
    p = fixture_db(tmp_path, 'same')
    with sqlite3.connect(p) as c:
        c.execute('UPDATE clock_domains SET reset_kind=NULL')
    assert run_on(p, structural.analyze)['findings'] == []


def test_verible_adjacent_categories():
    result = native.parse('verible', 'a.sv:1:2: Use always_comb [Style: combinational-logic][always-comb]')
    assert result[0]['rule'] == 'verible.always-comb'
