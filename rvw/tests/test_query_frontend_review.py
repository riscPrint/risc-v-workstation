"""Declared packed-bit identities from native HDL frontends."""
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
