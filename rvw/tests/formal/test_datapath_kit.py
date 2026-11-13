import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import pytest
from rvw.formal.datapath_kit import propose

pytestmark=pytest.mark.fast
ROOT=Path(__file__).resolve().parents[3]


def database(tmp_path):
    path=tmp_path/'design.db'
    conn=sqlite3.connect(path)
    conn.executescript((ROOT/'rvw/src/rvw/query/schema.sql').read_text())
    conn.execute("INSERT INTO meta VALUES ('schema','rvw.designdb/20')")
    conn.execute("INSERT INTO components(id,path,name,module,class_name,depth) VALUES(1,'cpu.mul','mul','Multiplier','MulUnit',1)")
    for index,(name,direction,width) in enumerate([('a','in',32),('b','in',32),('y','out',32),('clk','in',1),('reset','in',1)]):
        conn.execute('INSERT INTO signals(id,component_id,name,path,kind,direction,width) VALUES(?,1,?,?,\'wire\',?,?)',(index+1,name,'cpu.mul.'+name,direction,width))
    conn.commit()
    return path,conn


def test_hints_propose_but_never_confirm(tmp_path):
    _,conn=database(tmp_path)
    result=propose(SimpleNamespace(conn=conn),'mul',32)
    c=result['candidates'][0]
    assert result['status']=='needs_confirmation' and result['proof_ran'] is False
    assert c['binding']=={'top':'Multiplier','ports':{'a':'a','b':'b','y':'y','clk':'clk','reset':'reset'}}
    assert c['missing_roles']==[] and c['requires_confirmation'] is True
    assert c['width_consistent']
    assert propose(SimpleNamespace(conn=conn),'div',32)['status']=='no_candidates'
    conn.close()


def test_ambiguity_and_width_are_not_guessed(tmp_path):
    _,conn=database(tmp_path)
    conn.execute("INSERT INTO signals(id,component_id,name,path,kind,direction,width) VALUES(99,1,'lhs','cpu.mul.lhs','wire','in',32)")
    candidate=propose(SimpleNamespace(conn=conn),'mul',32)['candidates'][0]
    assert candidate['ambiguous_roles']['a']==['a','lhs']
    assert 'a' not in candidate['binding']['ports']
    candidate=propose(SimpleNamespace(conn=conn),'mul',64)['candidates'][0]
    assert candidate['missing_roles']==['a','y','b']
    conn.close()


def test_cli_uses_captured_database(tmp_path):
    from rvw.cli import main
    path,conn=database(tmp_path)
    conn.close()
    out=tmp_path/'kit'
    assert main(['formal','datapath','--unit','mul','--db',str(path),'--out',str(out),'--json'])==0
    result=json.loads((out/'proposal.json').read_text())
    assert result['input_capture'] and result['candidates'][0]['binding']['top']=='Multiplier'
    assert main(['formal','datapath','--out',str(tmp_path/'no-proof')])==2
    assert not (tmp_path/'no-proof').exists()


def test_cli_finds_default_database(tmp_path,monkeypatch):
    from rvw.cli import main
    path,conn=database(tmp_path);conn.close()
    monkeypatch.setenv('RVW_DESIGNDB',str(path))
    assert main(['formal','datapath','--unit','mul','--out',str(tmp_path/'default')])==0
    assert (tmp_path/'default/proposal.json').exists()
