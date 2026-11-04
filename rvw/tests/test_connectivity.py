"""Independent graph cases. No solver or full-core result is implied."""
import json
import shutil
import sqlite3

import pytest

from rvw.cli import main
from rvw.formal.connectivity import resolve
from rvw.query.db import DesignDB


@pytest.fixture
def db(gcd_db):
    design = DesignDB(gcd_db)
    yield design
    design.close()


def rule(**changes):
    return dict(id='transfer', kind='required', source='io_a', destination='io_result', **changes)


def test_required_path_is_not_a_proof(db):
    result = resolve(db, rule(latency=1))
    assert result['structural_status'] == 'dependency_found'
    assert [r['signal'] for r in result['path']] == ['io_a', 'x', 'io_result']
    assert result['status'] == 'incomplete'
    assert result['semantic_status'] == 'not_run'


def test_forbidden_path_and_absence(db):
    declaration = rule()
    declaration['kind'] = 'forbidden'
    assert resolve(db, declaration)['structural_status'] == 'dependency_found'
    declaration['destination'] = 'io_a'
    declaration['source'] = 'io_result'
    result = resolve(db, declaration)
    assert result['structural_status'] == 'dependency_absent'
    assert result['status'] == 'incomplete'


def test_missing_endpoint_is_incomplete(db):
    declaration = rule()
    declaration['source'] = 'missing'
    result = resolve(db, declaration)
    assert result['structural_status'] == 'incomplete'
    assert 'no signal' in result['reason']


def test_conditions_are_resolved(db):
    result = resolve(db, rule(mode='io_loadValues', enable='io_loadValues'))
    assert result['conditions'] == {'mode': 'io_loadValues', 'enable': 'io_loadValues'}
    assert result['semantic_status'] == 'not_run'
    assert resolve(db, rule(mode='io_a'))['structural_status'] == 'incomplete'
    assert resolve(db, rule(enable='missing'))['structural_status'] == 'incomplete'


def test_truncation_is_not_absence(db):
    result = resolve(db, rule(), max_nodes=1)
    assert result['truncated']
    assert result['structural_status'] == 'incomplete'


@pytest.mark.parametrize('kind', ['cond', 'sel', 'blackbox', 'reset', 'clock', 'init'])
def test_control_and_opaque_routes(gcd_db, tmp_path, kind):
    path = tmp_path/'mutated.db'
    shutil.copyfile(gcd_db, path)
    con = sqlite3.connect(path)
    src, dst = [con.execute('SELECT id FROM signals WHERE name=?', (n,)).fetchone()[0]
                for n in ('io_result', 'io_a')]
    con.execute('INSERT INTO edges VALUES (?, ?, ?)', (src, dst, kind))
    con.commit()
    con.close()
    design = DesignDB(path)
    try:
        declaration = dict(id='forbidden', kind='forbidden', source='io_result', destination='io_a')
        result = resolve(design, declaration)
        assert result['structural_status'] == ('incomplete' if kind == 'blackbox' else 'dependency_found')
        assert result['status'] == 'incomplete'
    finally:
        design.close()


def test_alternate_blackbox_route(gcd_db, tmp_path):
    path = tmp_path/'opaque.db'
    shutil.copyfile(gcd_db, path)
    con = sqlite3.connect(path)
    # The direct known route does not discharge an opaque alternate route.
    con.execute('UPDATE components SET blackbox=1')
    con.commit()
    con.close()
    design = DesignDB(path)
    try:
        assert resolve(design, rule())['structural_status'] == 'incomplete'
    finally:
        design.close()


@pytest.mark.parametrize('latency', [-1, True, '1'])
def test_bad_latency(db, latency):
    with pytest.raises(ValueError, match='latency'):
        resolve(db, rule(latency=latency))


def test_cli_captures_inputs_and_never_passes(gcd_db, tmp_path):
    plan = tmp_path/'connections.toml'
    plan.write_text('[[connection]]\nid="a"\nkind="required"\nsource="io_a"\ndestination="io_result"\nlatency=1\n')
    out = tmp_path/'out'
    assert main(['formal', 'connectivity', str(plan), '--db', str(gcd_db), '--out', str(out)]) == 1
    result = json.loads((out/'result.json').read_text())
    assert result['status'] == 'incomplete'
    assert len(result['database_sha256']) == 64
    assert len(result['input_capture']['files']) == 2


def test_unknown_declaration_field_is_refused(db):
    with pytest.raises(ValueError, match='unknown connection fields'):
        resolve(db, rule(mode_value=0))


def test_identity_and_cycle(db):
    declaration = rule()
    declaration['source'] = 'x'
    declaration['destination'] = 'x'
    result = resolve(db, declaration)
    assert result['structural_status'] == 'dependency_found'
    assert result['path'] == [{'signal': 'x', 'kind': None}]


def test_ambiguous_endpoint_is_incomplete(cluster_db):
    design = DesignDB(cluster_db)
    try:
        declaration = rule()
        declaration['source'] = 'x'
        result = resolve(design, declaration)
        assert result['structural_status'] == 'incomplete'
        assert 'ambiguous' in result['reason']
        assert len(result['candidates']) > 1
    finally:
        design.close()


def test_harness_samples_conditions_and_clears_valid(db):
    from rvw.formal.connectivity import harness
    text = harness(db, rule(latency=1, mode='io_loadValues', enable='io_loadValues'))
    assert 'if (reset) valid_0 <= 0' in text
    assert 'else valid_0 <= (p2 && p2)' in text
    assert 'if (!reset && valid_0)' in text
    assert '== expected_0' in text


@pytest.mark.parametrize('kind,latency,wrong,inactive,stale', [
    ('required', 0, False, False, False), ('required', 0, True, False, False),
    ('required', 1, False, False, False), ('required', 1, True, False, False),
    ('forbidden', 0, False, False, False), ('forbidden', 0, True, False, False),
    ('forbidden', 1, False, False, False), ('forbidden', 1, True, False, False),
    ('required', 1, False, True, False),
    ('required', 0, False, False, True),
])
def test_native_contract(gcd_db, tmp_path, kind, latency, wrong, inactive, stale):
    import hashlib
    if any(not shutil.which(t) for t in ('yosys', 'sby', 'yices-smt2')):
        pytest.skip('native Yosys, SBY and Yices required')
    path = tmp_path/'fixture.db'
    shutil.copyfile(gcd_db, path)
    data = 'io_a' if kind == 'required' or wrong else 'io_b'
    if kind == 'required' and wrong:
        data = 'io_a ^ 32\'h1'
    body = (f'always @(posedge clk) if (reset) io_result <= 0; '
            f'else io_result <= mode && io_loadValues ? ({data}) : 0;'
            if latency else f'always @* io_result = mode && io_loadValues ? ({data}) : 0;')
    if inactive:
        body += '\nalways @* assume(!mode);'
    rtl = tmp_path/'GCD.v'
    rtl.write_text('module GCD(input clk, reset, input [31:0] io_a, io_b, '
                   'input io_loadValues, mode, output reg [31:0] io_result);\n'+body+'\nendmodule\n')
    con = sqlite3.connect(path)
    con.execute("UPDATE signals SET name='mode', path='mode', spinal_path='mode', direction='in' WHERE name='io_resultIsValid'")
    con.execute('DELETE FROM edges')
    a, b = [con.execute('SELECT id FROM signals WHERE name=?', (n,)).fetchone()[0]
            for n in ('io_a', 'io_result')]
    con.execute("INSERT INTO edges VALUES (?, ?, 'data')", (a, b))
    con.execute('DELETE FROM rtl_files')
    con.execute('INSERT INTO rtl_files VALUES (?)', (str(rtl),))
    con.execute('INSERT INTO input_files VALUES (?, ?, ?, ?, ?)',
                (str(rtl), str(rtl.resolve()), hashlib.sha256(rtl.read_bytes()).hexdigest(), rtl.stat().st_size, '{}'))
    con.commit()
    con.close()
    if stale:
        rtl.write_text(rtl.read_text() + '// changed after extraction\n')
    plan = tmp_path/'connections.toml'
    plan.write_text(f'[[connection]]\nid="a"\nkind="{kind}"\nsource="io_a"\ndestination="io_result"\n'
                    f'latency={latency}\nmode="mode"\nenable="io_loadValues"\n')
    out = tmp_path/'out'
    assert main(['formal', 'connectivity', str(plan), '--db', str(path), '--out', str(out),
                 '--run', '--depth', '6', '--timeout', '30']) == 1
    report = json.loads((out/'result.json').read_text())
    entry = report['connections'][0]
    if stale:
        assert 'campaign' not in entry
        assert 'content binding' in entry['reason']
        return
    assert 'campaign' in entry, entry
    assert entry['campaign']['status'] == ('incomplete' if wrong or inactive else 'bounded_pass'), entry
    assert entry['campaign']['observations']['activation']['status'] == ('pass' if inactive else 'fail')
    assert entry['campaign']['observations']['transfer']['status'] == ('fail' if wrong else 'pass')
    assert report['status'] == 'incomplete'


def test_internal_binding_stays_incomplete(db):
    from rvw.formal.connectivity import harness
    declaration = rule()
    declaration['source'] = 'x'
    with pytest.raises(ValueError, match='internal RTL binding'):
        harness(db, declaration)


def test_required_width_mismatch(db):
    declaration = rule()
    declaration['source'] = 'io_loadValues'
    result = resolve(db, declaration)
    assert result['structural_status'] == 'incomplete'
    assert 'widths differ' in result['reason']
