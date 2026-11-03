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
