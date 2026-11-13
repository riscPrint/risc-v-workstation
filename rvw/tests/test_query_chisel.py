"""Chisel front end of `rvw query build-hdl`: FIRRTL through firtool, locations back to Scala."""
import json
import os
from pathlib import Path
import shutil

import pytest

from rvw.query import ops
from rvw.query.db import DesignDB
from rvw.query.hdl import build_hdl
from rvw.query.hdl_chisel import chisel_names, line_map

DATA = Path(__file__).parent / 'data/chisel'  # Gen.scala and the Top.fir Chisel 6.5.0 emits for it
YOSYS = shutil.which('yosys')
CACHED = Path.home() / 'Library/Caches/org.chipsalliance.llvm-firtool/1.62.0/bin/firtool'
FIRTOOL = os.environ.get('RVW_FIRTOOL') or shutil.which('firtool') or (str(CACHED) if CACHED.exists() else None)
needs_firtool = pytest.mark.skipif(not (YOSYS and FIRTOOL), reason='native Yosys and firtool required (RVW_FIRTOOL)')


def test_line_map():
    text = ('module Acc(\t// Gen.scala:8:7\n'
            '  assign io_out = acc;\t// Gen.scala:8:7, :13:20\n'
            '  wire x;\t// src/a/B.scala:3:1, C.scala:4:2\n'
            '  wire y; // not a location\n')
    assert line_map(text) == {1: [('Gen.scala', 8)], 2: [('Gen.scala', 8), ('Gen.scala', 13)],
                              3: [('src/a/B.scala', 3), ('C.scala', 4)]}


def test_chisel_names():
    hgldd = {'objects': [
        {'kind': 'struct', 'obj_name': 'T_io', 'port_vars': [{'var_name': 'a', 'type_name': 'logic'},
                                                             {'var_name': 'y', 'type_name': 'logic',
                                                              'unpacked_range': [1, 0]}]},
        {'kind': 'module', 'obj_name': 'T', 'module_name': 'T', 'port_vars': [
            {'var_name': 'io', 'type_name': 'T_io', 'value': {'opcode': "'{", 'operands': [
                {'sig_name': 'io_a'}, {'opcode': "'{", 'operands': [{'sig_name': 'io_y_0'}, {'sig_name': '_tmp'}]}]}},
            {'var_name': 'r', 'value': {'sig_name': 'r'}}]}]}
    assert chisel_names(hgldd) == {'T': {'io_a': 'io.a', 'io_y_0': 'io.y.0', 'r': 'r'}}


@needs_firtool
def test_chisel_fir(tmp_path, capsys):
    from rvw.cli import main
    fir = tmp_path / 'Top.fir'
    shutil.copy(DATA / 'Top.fir', fir)
    scala = tmp_path / 'src'
    scala.mkdir()
    shutil.copy(DATA / 'Gen.scala', scala / 'Gen.scala')
    out = tmp_path / 'design.db'
    build_hdl([fir], 'Top', out, yosys=YOSYS, frontend='chisel', firtool=FIRTOOL, source_roots=[scala])
    db = DesignDB(out)
    try:
        assert db.meta['frontend'] == 'yosys-firtool' and 'firtool' in db.meta['firtool_version']
        assert [c['path'] for c in ops.hierarchy(db)['root']['children']] == ['mem_ext', 'units_0', 'units_1']
        gen = str(scala / 'Gen.scala')
        # Chisel names resolve; locations are Scala lines.
        w = ops.where(db, 'io.a.valid')
        assert 'status' not in w and w['signal']['path'] == 'io_a_valid' and w['signal']['loc'] == f'{gen}:21'
        assert ops.where(db, 'units_1.io.in.bits')['signal']['loc'] == f'{gen}:9'
        assert ops.component(db, 'units_0')['loc'] == f'{gen}:8'
        acc = ops.drivers(db, 'units_0.acc')
        assert acc['signal']['loc'] == f'{gen}:13'
        reg = acc['register']
        assert reg['clock'] == 'clock' and reg['reset']['kind'] == 'SYNC' and reg['reset']['value'] == '00000000'
        mem = ops.drivers(db, 'mem_ext.Memory')
        assert mem['signal']['kind'] == 'mem' and mem['memory']['depth'] == 4
        assert ops.path(db, 'io_a_bits', 'io_r')['found'] and ops.path(db, 'io_a_bits', 'io_y_1')['found']
        assert not ops.path(db, 'io_b', 'io_r')['found']
        # The emitted Verilog, its Scala line map and HGLDD are kept in the database.
        names = {r[0] for r in db.q('SELECT name FROM artifacts')}
        assert {'rtl/Top.sv', 'hgldd/Top.dd', 'hdl/source-map.json'} <= names
        inputs = {r[0] for r in db.q('SELECT path FROM input_files')}
        assert inputs == {str(fir), gen}
        assert not db.q("SELECT 1 FROM files WHERE path LIKE 'rtl/%'")
    finally:
        db.close()
    assert main(['query', 'export', 'hgldd/Top.dd', str(tmp_path / 'Top.dd'), '--db', str(out), '--json']) == 0
    assert json.loads((tmp_path / 'Top.dd').read_text())['HGLDD']['version']
    capsys.readouterr()


@needs_firtool
def test_chisel_matches_emitted_rtl(tmp_path):
    from test_query_hdl import _yosys_graph
    fir = tmp_path / 'Top.fir'
    shutil.copy(DATA / 'Top.fir', fir)
    out = tmp_path / 'design.db'
    build_hdl([fir], 'Top', out, yosys=YOSYS, frontend='chisel', firtool=FIRTOOL)
    db = DesignDB(out)
    try:
        rtl = []
        for name, content in db.q("SELECT name, content FROM artifacts WHERE name LIKE 'rtl/%'"):
            path = tmp_path / Path(name).name
            path.write_bytes(content)
            rtl.append(path)
        oracle = _yosys_graph(sorted(rtl), 'Top', tmp_path)
        for a in ('io_a_bits', 'io_a_valid', 'io_sel', 'io_b'):
            for b in ('io_r', 'io_y_0', 'io_y_1', 'units_0.acc'):
                assert ops.path(db, a, b)['found'] == oracle(a, b), (a, b)
        # Without a source root holding Gen.scala, no location claims a Scala file.
        assert not db.q("SELECT 1 FROM files WHERE path LIKE '%Gen.scala'")
    finally:
        db.close()


@needs_firtool
def test_chisel_refusals(tmp_path):
    out = tmp_path / 'design.db'
    out.write_bytes(b'previous database')
    bad = tmp_path / 'bad.fir'
    bad.write_text('FIRRTL version 3.3.0\ncircuit Top :\n  module Top :\n    output o : UInt<1>\n    connect o, x\n')
    with pytest.raises(ValueError, match='firtool failed'):
        build_hdl([bad], 'Top', out, yosys=YOSYS, frontend='chisel', firtool=FIRTOOL)
    with pytest.raises(ValueError, match='no include directories'):
        build_hdl([bad], 'Top', out, yosys=YOSYS, frontend='chisel', defines=['A'])
    assert out.read_bytes() == b'previous database'
