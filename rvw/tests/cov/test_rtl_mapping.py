import json
from rvw.cov.code import SourceMap, report


def test_hgldd_nested_fields_use_leaf_lines(tmp_path):
    loc = lambda line: {'file': 1, 'begin_line': line}
    document = {'HGLDD': {'file_info': ['Unit.scala']}, 'objects': [
        {'kind': 'struct', 'obj_name': 'Bundle', 'port_vars': [
            {'var_name': 'valid', 'type_name': 'logic', 'hgl_loc': loc(21)},
            {'var_name': 'payload', 'type_name': 'logic', 'hgl_loc': loc(22)}]},
        {'module_name': 'Unit', 'port_vars': [{'var_name': 'io', 'type_name': 'Bundle',
          'hgl_loc': loc(10), 'value': {'opcode': "'{", 'operands': [
              {'sig_name': 'io_valid'}, {'sig_name': 'io_payload'}]}}]}]}
    path = tmp_path / 'unit.dd'
    path.write_text(json.dumps(document))
    source = SourceMap(hgldd=[path])
    assert source.location({'t': 'toggle', 'page': 'v_toggle/Unit', 'o': 'io_payload[3]'})['line'] == 22
    assert source.location({'t': 'toggle', 'page': 'v_toggle/Unit', 'o': 'io_valid'})['line'] == 21
    assert source.location({'t': 'line', 'page': 'v_line/Unit', 'l': '1'}) is None


def test_instance_denominators_do_not_expand_wildcards():
    points = [{'id': str(i), 'fields': {'h': h}, 'count': 0} for i, h in enumerate(
        ['TOP.a', 'TOP.a', 'TOP.*.b', 'unknown'])]
    result = report({'points': points, 'tests': {}})
    assert result['instance_scope']['TOP.a']['exact_instance_denominator'] == 2
    assert result['instance_scope']['TOP.a']['unmapped_scala_points'] == 2
    assert result['instance_scope']['TOP.*.b']['exact_instance_denominator'] is None
    assert result['instance_scope']['unknown']['exact_instance_denominator'] is None
    assert result['scala_mapping']['denominator'] == 4


def test_hgldd_vector_fields_and_conflicting_documents(tmp_path):
    def document(line):
        return {'HGLDD': {'file_info': ['Unit.scala']}, 'objects': [
            {'module_name': 'Unit', 'port_vars': [
                {'type_name': 'logic', 'unpacked_range': [1, 0],
                 'hgl_loc': {'file': 1, 'begin_line': line},
                 'value': {'opcode': "'{", 'operands': [{'sig_name': 's_0'}, {'sig_name': 's_1'}]}}]}]}
    path = tmp_path / 'unit.dd'
    path.write_text(json.dumps(document(9)))
    source = SourceMap(hgldd=[path])
    for name in ('s_0', 's_1'):
        assert source.location({'t': 'toggle', 'page': 'v_toggle/Unit', 'o': name})['line'] == 9
    path.write_text(json.dumps([document(9), document(10)]))
    source = SourceMap(hgldd=[path])
    assert source.location({'t': 'toggle', 'page': 'v_toggle/Unit', 'o': 's_0'}) is None



def test_hgldd_conflicting_instance_override_does_not_choose_module_line(tmp_path):
    def var(line):
        return {'value': {'sig_name': 'state'}, 'hgl_loc': {'file': 1, 'begin_line': line}}
    doc = {'HGLDD': {'file_info': ['Unit.scala']}, 'objects': [
        {'module_name': 'Unit', 'port_vars': [var(1)]},
        {'module_name': 'Top', 'children': [
            {'module_name': 'Unit', 'name': 'a', 'port_vars': [var(2)]}]}]}
    path = tmp_path / 'unit.dd'
    path.write_text(json.dumps(doc))
    source = SourceMap(hgldd=[path])
    assert source.location({'t': 'toggle', 'page': 'v_toggle/Unit', 'o': 'state'}) is None



def test_native_fsm_pages_group_by_module():
    points = [{'id': kind, 'fields': {'page': f'v_{kind}/Unit', 't': kind}, 'count': 1}
              for kind in ('fsm_state', 'fsm_arc')]
    result = report({'points': points, 'tests': {}})
    assert result['modules']['Unit']['total'] == 2
    assert set(result['module_types']['Unit']) == {'fsm_arc', 'fsm_state'}


def test_conflicting_hdl_spans_do_not_bypass_hgldd_ambiguity(tmp_path):
    def document(line):
        return {'HGLDD': {'file_info': ['Unit.scala', 'Unit.v']}, 'objects': [
            {'module_name': 'Unit', 'port_vars': [
                {'value': {'sig_name': 'state'},
                 'hgl_loc': {'file': 1, 'begin_line': line},
                 'hdl_loc': {'file': 2, 'begin_line': 10}}]}]}
    path = tmp_path / 'unit.dd'
    path.write_text(json.dumps([document(9), document(20)]))
    source = SourceMap(hgldd=[path])
    assert source.location({'t': 'toggle', 'page': 'v_toggle/Unit',
                            'o': 'state', 'f': 'Unit.v', 'l': '10'}) is None


def test_exact_instance_override_resolves_deduplicated_toggle(tmp_path):
    def var(n):
        return {'value': {'sig_name': 'state'}, 'hgl_loc': {'file': 1, 'begin_line': n}}
    doc = {'HGLDD': {'file_info': ['Unit.scala']}, 'objects': [
        {'kind': 'module', 'module_name': 'Unit', 'port_vars': [var(1)]},
        {'kind': 'module', 'module_name': 'Top', 'children': [
            {'module_name': 'Unit', 'name': 'a', 'port_vars': [var(2)]},
            {'module_name': 'Unit', 'name': 'b', 'port_vars': [var(3)]}]}]}
    path = tmp_path / 'unit.dd'
    path.write_text(json.dumps(doc))
    source = SourceMap(hgldd=[path])
    fields = {'t': 'toggle', 'page': 'v_toggle/Unit', 'o': 'state'}
    assert source.location(dict(fields, h='TOP.Top.a'))['line'] == 2
    assert source.location(dict(fields, h='TOP.Top.b'))['line'] == 3
    assert source.location(dict(fields, h='TOP.Top.*')) is None


def test_database_declaration_mapping_requires_exact_rtl(tmp_path):
    import sqlite3
    from hashlib import sha256
    rtl = tmp_path / 'Top.v'
    rtl.write_text('  count <= 1;\n  if(count == 0) begin\n')
    db = tmp_path / 'design.db'
    with sqlite3.connect(db) as c:
        c.executescript('''CREATE TABLE meta(key,value); CREATE TABLE files(id,path);
            CREATE TABLE components(id,path,module); CREATE TABLE signals(component_id,name,file_id,line,pruned);''')
        c.executemany('INSERT INTO meta VALUES (?,?)', [
            ('schema', 'rvw.designdb/20'), ('input_capture', json.dumps({'files': [
                {'resolved': str(rtl), 'sha256': sha256(rtl.read_bytes()).hexdigest()}]}))])
        c.execute("INSERT INTO components VALUES (0,'','Top')")
        c.execute("INSERT INTO components VALUES (1,'child','Child')")
        c.execute("INSERT INTO files VALUES (1,'Counter.scala')")
        c.execute("INSERT INTO signals VALUES (1,'count',1,42,0)")
        c.execute('CREATE TABLE memories(component_id,key,file_id,line)')
        c.execute('INSERT INTO memories VALUES (1,?,1,50)',
                  ('tag spinal.core.MemSymbolesTag:["ram_symbol0":Range(0,8,1,false)]',))
    fields = {'f': str(rtl), 'l': '1', 'h': 'TOP.Top.child', 'S': '1'}
    assert SourceMap(design_db=db).location(fields)['line'] == 42
    assert SourceMap(design_db=db).location(dict(fields, h='custom.prefix.Top.child'))['line'] == 42
    assert SourceMap(design_db=db).location(dict(fields, h='TOP.Other.child')) is None
    toggle = dict(fields, t='toggle', o='count[2][0]')
    assert SourceMap(design_db=db).location(toggle)['method'] == 'designdb-instance-declaration'
    assert SourceMap(design_db=db).location(dict(fields, t='toggle', o='ram_symbol0[7][0]'))['line'] == 50
    assert SourceMap(design_db=db).location(dict(fields, t='toggle', o='ram_symbol1[7][0]', l='3', S='3')) is None
    branch = SourceMap(design_db=db).location(dict(fields, l='2', S='2'))
    assert branch['line'] == 42
    assert branch['method'] == 'covered-span-declarations'
    alias = tmp_path / 'stable-copy.v'
    alias.write_bytes(rtl.read_bytes())
    assert SourceMap(design_db=db).location(dict(fields, f=str(alias)))['line'] == 42
    rtl.write_text('  count <= 2;\n')
    import pytest
    with pytest.raises(ValueError, match='RTL differs'):
        SourceMap(design_db=db).location(fields)


def test_hgldd_multidimensional_vec_of_struct(tmp_path):
    def aggregate(items):
        return {'opcode': "'{", 'operands': items}
    doc = {'HGLDD': {'file_info': ['Unit.scala']}, 'objects': [
        {'kind': 'struct', 'obj_name': 'Entry', 'port_vars': [
            {'hgl_loc': {'file': 1, 'begin_line': 7}},
            {'hgl_loc': {'file': 1, 'begin_line': 8}}]},
        {'module_name': 'Unit', 'port_vars': [{'type_name': 'Entry',
            'unpacked_range': [1, 0, 2, 0], 'value': aggregate([
                aggregate([aggregate([{'sig_name': f'v_{i}_{j}'}, {'sig_name': f'p_{i}_{j}'}])
                           for j in range(3)]) for i in range(2)])}]}]}
    path = tmp_path / 'vec.dd'
    path.write_text(json.dumps(doc))
    source = SourceMap(hgldd=[path])
    for i in range(2):
        for j in range(3):
            assert source.location({'t': 'toggle', 'page': 'v_toggle/Unit', 'o': f'v_{i}_{j}'})['line'] == 7
            assert source.location({'t': 'toggle', 'page': 'v_toggle/Unit', 'o': f'p_{i}_{j}'})['line'] == 8
