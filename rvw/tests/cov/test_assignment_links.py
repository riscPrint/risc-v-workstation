import json
import sqlite3
from hashlib import sha256
import pytest
from rvw.cov.code import SourceMap, report


def database(tmp_path, assignments):
    rtl = tmp_path / 'Top.v'
    rtl.write_text('assign data = 1;\n')
    db = tmp_path / 'design.db'
    with sqlite3.connect(db) as c:
        c.executescript('''CREATE TABLE meta(key,value); CREATE TABLE files(id,path);
            CREATE TABLE components(id,path,module);
            CREATE TABLE signals(id,component_id,name,file_id,line,pruned);
            CREATE TABLE assignments(target_id,component_id,kind,"range",file_id,line);''')
        c.executemany('INSERT INTO meta VALUES (?,?)', [
            ('schema', 'rvw.designdb/20'), ('input_capture', json.dumps({'files': [
                {'resolved': str(rtl), 'sha256': sha256(rtl.read_bytes()).hexdigest()}]}))])
        c.execute("INSERT INTO components VALUES (1,'','Top')")
        c.execute("INSERT INTO files VALUES (1,'Top.scala')")
        c.execute("INSERT INTO signals VALUES (1,1,'data',1,3,0)")
        c.executemany('INSERT INTO assignments VALUES (1,1,?,?,1,?)', assignments)
    return SourceMap(design_db=db), {'f': str(rtl), 'l': '1', 'S': '1', 't': 'line', 'h': 'TOP.Top'}


def test_unique_assignment_links_statement_location(tmp_path):
    source, fields = database(tmp_path, [('data', None, 42)])
    loc = source.location(fields)
    assert loc['line'] == 42
    assert loc['method'] == 'covered-span-assignment-links'
    result = report({'points': [{'id': 'x', 'fields': fields, 'count': 1, 'scala': loc}], 'tests': {}})
    assert result['scala_mapping']['methods'] == {'covered-span-assignment-links': 1}
    assert result['scala_mapping']['statement_hit_status'] == 'undetermined'


@pytest.mark.parametrize('assignments', [
    [('data', None, 42), ('data', None, 43)],
    [('data', None, 42), ('init', None, 10)],
    [('data', '(7 downto 0)', 42)], [('init', None, 10)]])
def test_ambiguous_assignments_keep_declaration_navigation(tmp_path, assignments):
    source, fields = database(tmp_path, assignments)
    loc = source.location(fields)
    assert loc['line'] == 3
    assert loc['method'] == 'covered-span-declarations'


def test_wildcards_and_toggles_cannot_earn_assignment_links(tmp_path):
    source, fields = database(tmp_path, [('data', None, 42)])
    assert source.location(dict(fields, h='TOP.Top.*')) is None
    assert source.location(dict(fields, t='toggle', o='data'))['method'] == 'designdb-instance-declaration'


def test_inline_always_assignment_is_an_exact_target(tmp_path):
    source, fields = database(tmp_path, [('data', None, 42)])
    # Rebind the same-elaboration fixture to an inline combinational assignment.
    rtl = tmp_path / 'Top.v'
    rtl.write_text('always @(*) data = 1;\n')
    with sqlite3.connect(tmp_path / 'design.db') as c:
        capture = {'files': [{'resolved': str(rtl), 'sha256': sha256(rtl.read_bytes()).hexdigest()}]}
        c.execute("UPDATE meta SET value=? WHERE key='input_capture'", (json.dumps(capture),))
    loc = SourceMap(design_db=tmp_path / 'design.db').location(fields)
    assert loc['line'] == 42
    assert loc['method'] == 'covered-span-assignment-links'
