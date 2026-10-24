import json
import sqlite3

import pytest

from rvw.cov.code import SourceMap, merge
from rvw.common.capture import sha256_file
from rvw.cov.mutation import mutation_report
from rvw.cov.proof import apply_exclusions
from .test_code import dat


def test_hgldd_one_based_signal_mapping_not_module_guess(tmp_path):
    path = tmp_path / 'tiny.dd'
    path.write_text(json.dumps({"HGLDD": {"file_info": ["Unit.scala"]}, "objects": [
        {"module_name": "Unit", "port_vars": [{"var_name": "a", "value": {"sig_name": "io_a"},
         "hgl_loc": {"file": 1, "begin_line": 42}}]}]}))
    source = SourceMap(tmp_path, hgldd=[path])
    loc = source.location({'f': 'Unit.v', 'l': '3', 't': 'toggle', 'page': 'v_toggle/Unit', 'o': 'io_a[2]:0->1'})
    assert loc == {'file': 'Unit.scala', 'line': 42, 'method': 'hgldd-signal-declaration'}
    assert source.location({'f': 'Unit.v', 'l': '3', 't': 'branch', 'page': 'v_branch/Unit'}) is None


def test_cover_fail_alone_never_excludes(tmp_path):
    (tmp_path / 'logic.v').write_text('module logic; endmodule\n')
    data = merge([str(dat(tmp_path / 'a.dat', [0]))], tmp_path)
    evidence = {"schema": "rvw.coverage-exclusions/7", "point_universe": data['point_universe'], "dependencies": {},
                "files": {},
                "inputs": {str(tmp_path / 'logic.v'): sha256_file(tmp_path / 'logic.v')},
                "points": [{"point_id": data['points'][0]['id'], "unreachable": True,
                 "jobs": {"prove": {"status": "UNKNOWN", "exit_code": 0}, "cover": {"status": "FAIL"}}}]}
    file = tmp_path / 'exclusions.json'
    file.write_text(json.dumps(evidence))
    with pytest.raises(ValueError, match='unbounded proofs'):
        apply_exclusions(data, file)


def test_mutation_controls_equivalence_and_pending_are_not_kills(tmp_path):
    (tmp_path / 'database').mkdir()
    (tmp_path / 'config.mcy').write_text('[options]\nsize 4\n')
    with sqlite3.connect(tmp_path / 'database/db.sqlite3') as db:
        db.executescript('CREATE TABLE mutations(mutation_id INTEGER, mutation TEXT);'
                         'CREATE TABLE tags(mutation_id INTEGER, tag TEXT);'
                         'CREATE TABLE results(mutation_id INTEGER, test TEXT, result TEXT);'
                         'CREATE TABLE queue(mutation_id INTEGER, test TEXT, running INTEGER);')
        db.executemany('INSERT INTO mutations VALUES(?,?)', [(1, 'mutate -mode none'), (2, 'mutate -mode inv'),
                                                              (3, 'mutate -mode inv'), (4, 'mutate -mode inv')])
        db.executemany('INSERT INTO results VALUES(?,?,?)', [(1, 'sim', 'PASS'), (1, 'eq', 'PASS'), (2, 'sim', 'PASS'), (2, 'eq', 'FAIL'),
                                                            (3, 'sim', 'PASS'), (3, 'eq', 'PASS')])
        db.execute('INSERT INTO queue VALUES(4,"sim",0)')
    result = mutation_report(tmp_path, ['sim'], ['eq'])
    assert result['status'] == 'inconclusive'
    assert result['cause'] == 'input_not_captured:mcy_dependencies'
    assert [p['observed_state'] for p in result['mutants']] == ['control', 'survived', 'equivalent', 'pending']
    assert [p['state'] for p in result['mutants']] == ['inconclusive'] * 3 + ['pending']
    assert all(result['counts'][state] == 0 for state in ('killed', 'survived', 'equivalent', 'control'))
