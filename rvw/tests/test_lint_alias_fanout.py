"""Alias bit nodes are connectivity, not hardware loads."""
import pytest
from lint_builder import Builder
from rvw.lint import rules
from rvw.query.db import run_on

pytestmark=pytest.mark.fast


def test_alias_vector_fanout_keeps_real_loads(tmp_path):
    b=Builder(tmp_path/'d.db')
    b.c.execute("INSERT INTO meta VALUES('frontend','yosys-verilog')")
    b.sig('bus',width=8,direction='in')
    for n in range(8):
        bit=f'bit{n}';b.sig(bit)
        b.edge('bus',bit);b.edge(bit,'bus')
        b.assign('bus','alias',source='Yosys net alias')
        b.c.execute('INSERT INTO assign_reads VALUES(?,?,?)',(b.assign_id,b.ids[bit],'data'))
    # Three real loads behind one alias bit still exceed a limit of two.
    for n in range(3):
        b.sig(f'load{n}',direction='out');b.edge('bit0',f'load{n}')
    db=b.done()
    for limit,wanted in [(4,False),(2,True)]:
        result=run_on(db,lambda d:rules.analyze(d,{'lint.max_fanout':{'limit':limit}}))
        rows=[f for f in result['findings'] if f['rule']=='lint.max_fanout' and f['endpoint']=='bus']
        assert bool(rows)==wanted
        if rows:assert rows[0]['fanout']==3
