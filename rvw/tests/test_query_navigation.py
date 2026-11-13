import json
import shutil
import sqlite3
import pytest
from rvw.query.db import DesignDB
from rvw.query.navigation import navigation

pytestmark = pytest.mark.fast


def test_navigation(gcd_db, tmp_path):
    copied = tmp_path / "design.db"
    shutil.copyfile(gcd_db, copied)
    gcd_db = copied
    conn = sqlite3.connect(gcd_db)
    diagram = {'modules': {'GCD': {'nodes': [{'id': 'area:calc', 'signals': [{'name': 'x'}]}]}}}
    conn.execute("INSERT OR REPLACE INTO artifacts(name,encoding,content) VALUES(?,?,?)",
                 ('blocks.json', 'identity', json.dumps(diagram).encode()))
    conn.commit()
    conn.close()
    db = DesignDB(gcd_db)
    try:
        r = navigation(db, 'x')
        assert r['source']['line']
        assert r['block']['endpoints'] == [{'kind': 'node', 'id': 'area:calc'}]
        assert r['wave']['path'] == 'TOP.GCD.x'
        assert r['trace']['signal'] == 'signal:x'
        assert r['schema'] == 'rvw.navigation/1'
        assert navigation(db, 'y')['block']['status'] == 'unmapped'
    finally:
        db.close()
