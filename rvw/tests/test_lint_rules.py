"""RTL lint rules on small exact-schema graphs, severities, waivers and SARIF."""
import json
import pytest
from lint_builder import Builder
from rvw.cli import main
from rvw.lint import rules
from rvw.lint.cli import report
from rvw.query.db import run_on


pytestmark = pytest.mark.fast


def lint(db, config=None):
    return run_on(db, lambda d: rules.analyze(d, config))


def found(r):
    return {(f['rule'], f['endpoint']) for f in r['findings']}


def base(tmp_path):
    b = Builder(tmp_path / 'd.db')
    b.domain(1, clock='clk', reset='rst', kind='SYNC')
    b.sig('clk', direction='in', role='clock')
    b.sig('rst', direction='in', role='reset')
    b.sig('i', direction='in')
    b.sig('o', direction='out')
    return b


def test_structure_rules(tmp_path):
    b = base(tmp_path)
    b.sig('loopA'); b.sig('loopB')
    b.chain('i', 'loopA', 'loopB', 'loopA')
    b.assign('loopA', ' := x'); b.assign('loopB', ' := y')
    b.sig('self'); b.edge('self', 'self'); b.assign('self', ' := self')
    b.sig('floating')
    b.sig('dead'); b.edge('i', 'dead'); b.assign('dead', ' := i:Bool')
    b.reg('noReset', 1, init=None); b.edge('i', 'noReset'); b.assign('noReset', ' := i:Bool')
    b.edge('noReset', 'o'); b.assign('o', ' := noReset:Bool')
    b.reg('stuck', 1)
    b.edge('stuck', 'o')
    b.sig('latch'); b.edge('i', 'latch'); b.assign('latch', ' := i:Bool', cond=1); b.edge('latch', 'o')
    b.reg('clocked', 1); b.edge('clk', 'clocked'); b.assign('clocked', ' := clk:Bool'); b.edge('clocked', 'o')
    b.sig('narrow', width=3); b.edge('i', 'narrow'); b.edge('narrow', 'o')
    b.assign('narrow', ' := ResizeBits<3>[3](wide:Bits[8])')
    b.sig('wider', width=8); b.edge('i', 'wider'); b.edge('wider', 'o')
    b.assign('wider', ' := ResizeUInt<8>[8](Operator$UInt$Add[4](a:UInt[4],b:UInt[4]))')
    b.assign('i', ' := lit:Bool=true')
    b.component('child', 'Child')
    b.sig('child.out', direction='out', comp='child')
    b.sig('child.x', comp='child'); b.edge('child.x', 'o')
    b.assign('child.x', ' := a', comp='child'); b.assign('child.x', ' := b', comp='')
    b.sig('logic', name='logic'); b.edge('i', 'logic'); b.edge('logic', 'o'); b.assign('logic', ' := i:Bool')
    r = lint(b.done())
    f = found(r)
    assert ('lint.comb_loop', 'loopA') in f and ('lint.comb_loop', 'self') in f
    assert ('lint.undriven', 'floating') in f
    assert ('lint.unused', 'dead') in f
    assert ('lint.no_reset', 'noReset') in f
    assert ('lint.constant_register', 'stuck') in f
    assert ('lint.latch', 'latch') in f
    assert ('lint.clock_as_data', 'clocked') in f
    assert ('lint.width_truncation', 'narrow') in f and ('lint.width_extension', 'wider') in f
    assert ('lint.input_driven', 'i') in f
    assert ('lint.unconnected_output', 'child.out') in f
    assert ('lint.multiple_drivers', 'child.x') in f
    assert ('lint.naming', 'logic') in f
    assert ('lint.undriven', 'clk') not in f and ('lint.unused', 'o') not in f
    loop = next(x for x in r['findings'] if x['rule'] == 'lint.comb_loop' and x['endpoint'] == 'loopA')
    assert loop['members'] == ['loopA', 'loopB'] and loop['severity'] == 'error'


def test_severity_settings_and_limits(tmp_path):
    b = base(tmp_path)
    b.reg('r', 1, init=None); b.edge('i', 'r'); b.edge('r', 'o')
    for n in range(4):
        b.sig(f'f{n}'); b.edge('i', f'f{n}'); b.edge(f'f{n}', 'o')
    b.sig('BadName'); b.edge('i', 'BadName'); b.edge('BadName', 'o')
    db = b.done()
    r = lint(db, {'lint.no_reset': 'error', 'lint.max_fanout': {'limit': 3},
                  'lint.naming': {'signals': '[a-z][a-z0-9]*'}})
    sev = {(f['rule'], f['endpoint']): f['severity'] for f in r['findings']}
    assert sev[('lint.no_reset', 'r')] == 'error'
    assert ('lint.max_fanout', 'i') in sev
    assert ('lint.naming', 'BadName') in sev
    assert not [f for f in lint(db, {'lint.no_reset': 'off'})['findings'] if f['rule'] == 'lint.no_reset']
    for bad in ({'lint.nope': 'error'}, {'lint.no_reset': 'loud'}, {'lint.max_fanout': {'limit': 0}},
                {'lint.naming': {'ports': '('}}):
        with pytest.raises(ValueError):
            lint(db, bad)


def test_fsm_unreachable(tmp_path):
    b = base(tmp_path)
    t = 'State@seq[2]{idle=0,run=1,done=2,lost=3}'
    lit = 'lit:enum State@seq[2]{{idle=0,run=1,done=2,lost=3}}.{}#{}'
    b.reg('state', 1, type_=t, width=2, init='idle')
    b.sig('next', type_=t, width=2)
    b.chain('next', 'state'); b.edge('state', 'next'); b.edge('state', 'o')
    b.assign('state', ' := next:enum[2]')
    b.assign('next', ' := state:enum[2]')
    b.assign('next', ' := ' + lit.format('run', 1), cond=1)
    b.assign('next', ' := ' + lit.format('done', 2), cond=2)
    for target, source in (('state', 'next'), ('next', 'state')):
        b.c.execute('INSERT INTO assign_reads SELECT a.id, s.id, \'data\' FROM assignments a, signals s '
                    'WHERE a.target_id=? AND s.id=? AND a.key NOT LIKE \'%lit:%\'', (b.ids[target], b.ids[source]))
    r = lint(b.done())
    row = r['fsm'][0]
    assert row['status'] == 'checked' and row['unreachable'] == ['lost']
    assert ('lint.fsm_unreachable', 'state') in found(r)


def test_backend_waiver_and_sarif(tmp_path, capsys):
    b = base(tmp_path)
    b.sig('floating')
    db = b.done()
    p = tmp_path / 'lint.json'
    cfg = dict(schema='rvw.lint-settings/1', config='c', top='Top', db=str(db), backends=['rules'],
               rules={'lint.input_driven': 'off'})
    p.write_text(json.dumps(cfg))
    r = report(p)
    f = next(x for x in r['backends']['rules']['findings'] if x['endpoint'] == 'floating')
    cfg['waivers'] = [dict(rule=f['rule'], endpoint='floating', finding_id=f['id'], config='c', reason='spare net')]
    p.write_text(json.dumps(cfg))
    sarif = tmp_path / 'out.sarif'
    assert main(['lint', '--settings', str(p), '--sarif', str(sarif), '--json']) in (0, 1, 3)
    out = json.loads(capsys.readouterr().out)
    assert out['waivers'][0]['matches'] == 1
    doc = json.loads(sarif.read_text())
    assert doc['version'] == '2.1.0'
    res = [x for x in doc['runs'][0]['results'] if x['properties']['endpoint'] == 'floating'][0]
    assert res['suppressions'][0]['justification'] == 'spare net'
    assert res['locations'][0]['physicalLocation']['region']['startLine'] >= 1
    assert res['fingerprints']['rvw/finding-id'] == f['id']
    cfg['rules'] = {'lint.unknown': 'error'}
    p.write_text(json.dumps(cfg))
    with pytest.raises(ValueError, match='unknown lint rule'):
        report(p)


def test_mcp_emit_tool(tmp_path):
    from rvw.lint.mcp_tools import mcp_tools
    from rvw.lint.cli import report_outputs
    tools = {t.name: t for t in mcp_tools()}
    assert set(tools) == {'lint_report', 'lint_emit'}
    assert tools['lint_emit'].input_schema['required'] == ['settings', 'out']
    b = base(tmp_path)
    db = b.done()
    p = tmp_path / 'lint.json'
    p.write_text(json.dumps(dict(schema='rvw.lint-settings/1', config='c', top='Top', db=str(db),
                                 backends=['rules', 'structural'])))
    r = report_outputs(str(p), emit_dir=str(tmp_path / 'e'), sarif_path=str(tmp_path / 'x.sarif'))
    assert (tmp_path / 'e/cdc_obligations.json').is_file() and (tmp_path / 'x.sarif').is_file()
    assert r['emitted']['obligations'] == 0


def test_exhaustive_condition_tree_is_not_a_latch(tmp_path):
    # Spinal: when(a) { x := i }.elsewhen(b) { x := j }.otherwise { x := k }
    b = base(tmp_path)
    b.sig('x'); b.edge('x', 'o')
    for i, parent, kind, key, line in [(1, None, 'when', 'a', 10), (2, None, 'else', 'a', 10),
                                       (3, 2, 'when', 'b', 11), (4, 2, 'else', 'b', 11)]:
        b.c.execute('INSERT INTO conds(id,parent_id,component_id,kind,key,file_id,line) VALUES(?,?,1,?,?,1,?)',
                    (i, parent, kind, key, line))
    for cond in (1, 3, 4):
        b.assign('x', ' := i:Bool', cond=cond)
    assert ('lint.latch', 'x') not in found(lint(b.done()))


def test_switch_default_must_assign_target(tmp_path):
    # Spinal: switch(sel) { is(0) { x := i }; default { y := i } }
    b = base(tmp_path)
    b.sig('x'); b.edge('x', 'o')
    for i, kind in [(1, 'case'), (2, 'default')]:
        b.c.execute('INSERT INTO conds(id,component_id,kind,signal_id,file_id,line) VALUES(?,1,?,1,1,10)', (i, kind))
    b.assign('x', ' := i:Bool', cond=1)
    assert ('lint.latch', 'x') in found(lint(b.done()))


def test_conditional_declaration_needs_lowered_rtl(tmp_path):
    b = base(tmp_path)
    b.sig('local', tags='spinaldb:conditionalDeclaration')
    b.assign('local', ' := i:Bool', cond=1)
    b.edge('local', 'o')
    r = lint(b.done())
    assert ('lint.latch', 'local') not in found(r)
    assert any(f['endpoint'] == 'local' for f in r['unresolved'])


def test_each_bit_needs_complete_assignment(tmp_path):
    b = base(tmp_path)
    b.sig('mask', width=2)
    for i, kind in [(1, 'when'), (2, 'else')]:
        b.c.execute('INSERT INTO conds(id,component_id,kind,key,file_id,line) VALUES(?,1,?,\'a\',1,10)', (i, kind))
    for bit in range(2):
        for cond in (1, 2):
            b.assign('mask', ' := i:Bool', cond=cond)
            b.c.execute('UPDATE assignments SET range=? WHERE id=?', (f'({bit})', b.assign_id))
    db = b.done()
    assert ('lint.latch', 'mask') not in found(lint(db))
    import sqlite3
    with sqlite3.connect(db) as c:
        c.execute("DELETE FROM assignments WHERE range='(1)' AND cond_id=2")
    assert ('lint.latch', 'mask') in found(lint(db))

def test_hashed_enum_literal_is_not_absence_evidence(tmp_path):
    b = base(tmp_path)
    b.reg('state', 1, type_='State@seq[1]{idle=0,run=1}', init='idle')
    b.assign('state', ' := h:abc123')
    r = lint(b.done())
    assert r['fsm'][0]['status'] == 'inconclusive'
    assert not [f for f in r['findings'] if f['rule'] == 'lint.fsm_unreachable']



def test_hashed_enum_source_keeps_exact_literals(tmp_path):
    b = base(tmp_path)
    b.reg('state', 1, type_='State@seq[2]{idle=0,run=1,lost=2}', width=2, init='idle')
    b.assign('state', ' := h:abc', source='State.idle')
    b.assign('state', ' := h:def', source='State.run', cond=1)
    r = lint(b.done())
    assert r['fsm'][0]['status'] == 'checked'
    assert r['fsm'][0]['unreachable'] == ['lost']


def test_resetless_cell_shares_a_resettable_clock(tmp_path):
    b = base(tmp_path)
    b.domain(2, clock='clk', kind='BOOT')
    b.reg('valid', 2, init=None, direction='out')
    b.assign('valid', ' := i:Bool'); b.edge('i', 'valid')
    r = lint(b.done())
    f = next(f for f in r['findings'] if f['endpoint'] == 'valid' and f['rule'] == 'lint.no_reset')
    assert f['severity'] == 'info'
