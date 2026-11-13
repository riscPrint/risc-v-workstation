"""Declared packed-bit identities and native frontend dependency parity."""
from pathlib import Path
import shutil
import pytest
from rvw.query.hdl import build_hdl
from rvw.query.db import DesignDB
from rvw.query import ops

YOSYS = shutil.which('yosys')

@pytest.mark.skipif(not YOSYS, reason='Yosys required')
@pytest.mark.parametrize('decl', ['[7:4]', '[4:7]'])
def test_declared_packed_bit_indices(tmp_path, decl):
    source = tmp_path / 'top.v'
    source.write_text(f'module top(input {decl} a, output hi, lo); assign hi=a[7]; assign lo=a[4]; endmodule')
    out = tmp_path / 'top.db'
    build_hdl([source], 'top', out)
    db = DesignDB(out)
    try:
        # Both visible aliases share these graph nodes; their names use the declaration range.
        assert db.resolve_one('a[7]').width == 1
        assert db.resolve_one('a[4]').width == 1
        assert ops.path(db, 'a[7]', 'hi')['found']
        assert not ops.path(db, 'a[7]', 'lo')['found']
        assert ops.path(db, 'a[4]', 'lo')['found']
    finally:
        db.close()

SLANG = Path(YOSYS).resolve().parents[1] / "share/yosys/plugins/slang.so" if YOSYS else Path("/absent")

@pytest.mark.skipif(not YOSYS or not SLANG.is_file(), reason='Yosys and slang required')
def test_frontends_agree_on_drivers_and_loads(tmp_path):
    source = tmp_path / 'top.v'
    source.write_text('module top(input a, b, output y, z); assign y = ~a; assign z = a & b; endmodule')
    results = []
    for frontend in ('yosys', 'slang'):
        out = tmp_path / (frontend + '.db')
        build_hdl([source], 'top', out, frontend=frontend)
        db = DesignDB(out)
        try:
            results.append({n: ({r['path'] for r in ops.drivers(db, n)['read_signals']},
                                {r['path'] for r in ops.loads(db, n)['readers']}) for n in ('a','b','y','z')})
        finally:
            db.close()
    assert results[0] == results[1] == {'a': (set(), {'y', 'z'}), 'b': (set(), {'z'}),
                                       'y': ({'a'}, set()), 'z': ({'a', 'b'}, set())}



@pytest.mark.skipif(not YOSYS, reason='Yosys required')
def test_real_feedback_is_retained(tmp_path):
    source = tmp_path / 'loop.v'
    source.write_text('module top(input a, output y); assign y = ~y & a; endmodule')
    out = tmp_path / 'loop.db'
    build_hdl([source], 'top', out)
    db = DesignDB(out)
    try:
        assert ops.path(db, 'y', 'y')['found']
        assert 'y' in {r['path'] for r in ops.drivers(db, 'y')['read_signals']}
    finally:
        db.close()
