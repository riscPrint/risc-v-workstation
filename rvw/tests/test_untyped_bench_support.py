import json
import sqlite3
import pytest
from rvw.cli import main
from rvw.uvm.scaffold import generate
from test_uvm_scaffold import fixture
pytestmark = pytest.mark.fast

def test_untyped_uvm_is_unsupported_for_cli_and_mcp(tmp_path, capsys):
    db, soc = fixture(tmp_path)
    with sqlite3.connect(db) as conn: conn.execute('DELETE FROM bundles')
    out = tmp_path / 'bench'
    assert generate(db, soc, out, profile='cpu')['status'] == 'unsupported'
    assert main(['uvm','new','--db',str(db),'--soc',str(soc),'--out',str(out),'--profile','cpu']) == 2
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'unsupported' and 'pin bindings' in result['reason']
    assert not out.exists()

def test_untyped_vip_never_writes_a_bench(gcd_db, tmp_path, capsys):
    from rvw.vip.catalog import buses, skeleton
    assert buses(gcd_db)['status'] == 'unsupported'
    out=tmp_path/'bench.py'
    assert skeleton(gcd_db,out)['status'] == 'unsupported'
    assert main(['vip','bench','--db',str(gcd_db),'--out',str(out)]) == 2
    assert json.loads(capsys.readouterr().out)['status'] == 'unsupported'
    assert not out.exists()
