"""GHDL front end of `rvw query build-hdl`: VHDL through the GHDL Yosys plugin."""
import json
import os
from pathlib import Path
import shutil

import pytest

from rvw.query import ops
from rvw.query.db import DesignDB
from rvw.query.hdl import build_hdl
from rvw.query.hdl_ghdl import entity_of, locations

YOSYS = shutil.which('yosys')
GHDL = shutil.which('ghdl')


def _has_plugin():
    if not (YOSYS and GHDL):
        return False
    if os.environ.get('RVW_GHDL_PLUGIN'):
        return True
    return (Path(os.path.realpath(YOSYS)).parents[1] / 'share/yosys/plugins/ghdl.so').is_file()


needs_ghdl = pytest.mark.skipif(not _has_plugin(), reason='native Yosys, GHDL and the GHDL Yosys plugin required')

PKG = """library ieee;
use ieee.std_logic_1164.all;
package defs is
  type bus_t is record
    data  : std_ulogic_vector(7 downto 0);
    valid : std_ulogic;
  end record;
end package;
"""
TOP = """library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.defs.all;

entity leaf is
  generic (W : natural := 8);
  port (
    clk_i  : in  std_ulogic;
    rstn_i : in  std_ulogic;
    d_i    : in  bus_t;
    q_o    : out std_ulogic_vector(W-1 downto 0));
end entity;

architecture rtl of leaf is
  signal acc : unsigned(W-1 downto 0);
begin
  process (clk_i, rstn_i)
  begin
    if rstn_i = '0' then
      acc <= (others => '0');
    elsif rising_edge(clk_i) then
      if d_i.valid = '1' then
        acc <= acc + unsigned(d_i.data(W-1 downto 0));
      end if;
    end if;
  end process;
  q_o <= std_ulogic_vector(acc);
end architecture;

library ieee;
use ieee.std_logic_1164.all;
use work.defs.all;

entity top is
  generic (N : natural := 2);
  port (
    clk_i  : in  std_ulogic;
    rstn_i : in  std_ulogic;
    a_i    : in  bus_t;
    b_i    : in  std_ulogic;
    y_o    : out std_ulogic_vector(8*N-1 downto 0));
end entity;

architecture rtl of top is
begin
  g : for i in 0 to N-1 generate
    u : entity work.leaf generic map (W => 8) port map (clk_i => clk_i, rstn_i => rstn_i, d_i => a_i, q_o => y_o(8*i+7 downto 8*i));
  end generate;
end architecture;
"""


def test_xml_locations():
    xml = """<root>
<library_unit kind="entity_declaration" file="/c/a.vhd" line="3" identifier="Leaf">
  <el kind="interface_signal_declaration" file="/c/a.vhd" line="5" identifier="clk_i"/>
</library_unit>
<library_unit kind="architecture_body" file="/c/a.vhd" line="9" identifier="rtl">
  <entity_name kind="simple_name" identifier="leaf"/>
  <el kind="signal_declaration" file="/c/a.vhd" line="10" identifier="acc"/>
  <el kind="simple_signal_assignment_statement" file="/c/a.vhd" line="14">
    <target kind="indexed_name"><prefix kind="simple_name" identifier="acc"/></target>
  </el>
</library_unit></root>"""
    locs = locations(xml)
    assert locs['entities'] == {'leaf': ('/c/a.vhd', 3)}
    assert locs['decls'][('leaf', 'clk_i')] == ('/c/a.vhd', 5)
    assert locs['decls'][('leaf', 'acc')] == ('/c/a.vhd', 10)
    assert locs['assigns'][('leaf', 'acc')] == [('/c/a.vhd', 14)]
    assert entity_of('leaf_Brtl_8', {'leaf': 0, 'top': 0}) == 'leaf'
    assert entity_of('cpu_alu_Bcpu_alu_rtl_Lneorv32_1_ab', {'cpu': 0, 'cpu_alu': 0}) == 'cpu_alu'
    assert entity_of('other', {'leaf': 0}) is None


def _design(tmp_path):
    (tmp_path / 'pkg.vhd').write_text(PKG)
    (tmp_path / 'top.vhd').write_text(TOP)
    return [tmp_path / 'pkg.vhd', tmp_path / 'top.vhd']


@needs_ghdl
def test_ghdl_design(tmp_path):
    sources = _design(tmp_path)
    out = tmp_path / 'design.db'
    build_hdl(sources, 'top', out, yosys=YOSYS, frontend='ghdl', parameters=['N=3'])
    db = DesignDB(out)
    try:
        assert db.meta['frontend'] == 'yosys-ghdl'
        assert json.loads(db.meta['hdl_options']) == {'std': '08', 'library': 'work', 'parameters': ['N=3']}
        kids = ops.hierarchy(db)['root']['children']
        assert [k['path'] for k in kids] == ['g:1.u', 'g:2.u', 'g:3.u']
        assert {k['module'] for k in kids} == {'leaf'}
        assert ops.component(db, 'g:2.u')['loc'] == f'{sources[1]}:6'
        acc = ops.where(db, 'g:2.u.acc')['signal']
        assert acc['kind'] == 'reg' and acc['loc'] == f'{sources[1]}:16'
        # GHDL inverts rstn_i for the flip-flop; the domain reports the input's own polarity.
        r = ops.drivers(db, 'g:1.u.acc')
        assert r['assignments'][0]['loc'] == f'{sources[1]}:21'
        sig = db.resolve_one('g:1.u.acc')
        cd = db.clock_domain(sig.clock_domain_id)
        assert cd['reset'] == 'rstn_i' and cd['reset_kind'] == 'ASYNC' and cd['reset_active'] == 'low'
        assert sig.reset_value == '00000000'
        assert ops.path(db, 'a_i[data]', 'y_o')['found'] and ops.path(db, 'a_i[valid]', 'y_o')['found']
        assert not ops.path(db, 'b_i', 'y_o')['found']
    finally:
        db.close()


@needs_ghdl
def test_ghdl_matches_netlist_oracle(tmp_path):
    from rvw.common.proc import run_group
    from rvw.query.hdl_ghdl import ghdl_prefix, plugin_path
    from test_query_slang import _oracle

    class T:
        resolved = os.path.realpath(YOSYS)
    sources = _design(tmp_path)
    out = tmp_path / 'design.db'
    build_hdl(sources, 'top', out, yosys=YOSYS, frontend='ghdl')
    netlist = tmp_path / 'oracle.json'
    script = tmp_path / 'oracle.ys'
    script.write_text(f'ghdl --std=08 {sources[0]} {sources[1]} -e top\nwrite_json {netlist}\n')
    env = {**os.environ, 'GHDL_PREFIX': ghdl_prefix(T) or ''}
    p = run_group([YOSYS, '-Q', '-T', '-m', str(plugin_path(T, None)), '-s', str(script)],
                  cwd=tmp_path, env=env, capture=True, timeout=60)
    assert p.returncode == 0, p.stderr
    oracle = _oracle(netlist, 'top')
    db = DesignDB(out)
    try:
        for a in ('a_i[data]', 'a_i[valid]', 'b_i', 'g:1.u.d_i[data]', 'g:2.u.acc'):
            for b in ('y_o', 'g:1.u.q_o', 'g:2.u.q_o', 'g:2.u.acc'):
                if a != b:
                    assert ops.path(db, a, b)['found'] == oracle(a, b), (a, b)
    finally:
        db.close()


@needs_ghdl
def test_ghdl_refusals(tmp_path):
    sources = _design(tmp_path)
    out = tmp_path / 'design.db'
    out.write_bytes(b'previous database')
    with pytest.raises(ValueError, match='include directories or defines'):
        build_hdl(sources, 'top', out, yosys=YOSYS, frontend='ghdl', defines=['A'])
    with pytest.raises(ValueError, match='VHDL standard'):
        build_hdl(sources, 'top', out, yosys=YOSYS, frontend='ghdl', std='2099')
    with pytest.raises(ValueError, match='failed'):
        build_hdl(sources[1:], 'top', out, yosys=YOSYS, frontend='ghdl')  # package missing
    assert out.read_bytes() == b'previous database'


@pytest.fixture(scope='module')
def memory_plugin(tmp_path_factory):
    """Probe the installed plugin's Yosys memory ABI before the real designs."""
    root = tmp_path_factory.mktemp('ghdl-memory-probe')
    source = root / 'memory.vhd'
    source.write_text("""library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
entity memory_probe is
  port(clk, we: in std_logic; addr: in unsigned(3 downto 0);
       d: in std_logic_vector(7 downto 0); q: out std_logic_vector(7 downto 0));
end;
architecture rtl of memory_probe is
  type ram_t is array (0 to 15) of std_logic_vector(7 downto 0);
  signal ram: ram_t;
begin
  process(clk) begin
    if rising_edge(clk) then
      if we = '1' then ram(to_integer(addr)) <= d; end if;
      q <= ram(to_integer(addr));
    end if;
  end process;
end;
""")
    try:
        build_hdl([source], 'memory_probe', root / 'probe.db', yosys=YOSYS, frontend='ghdl')
    except ValueError as error:
        detail = str(error)
        if 'internal cell' in detail and '$memwr_v2' in detail:
            pytest.skip('installed GHDL plugin has an incompatible Yosys memory ABI; '
                        'rebuild with python3 scripts/build-ghdl-plugin.py and set RVW_GHDL_PLUGIN')
        raise


@needs_ghdl
def test_neorv32_cpu(tmp_path, memory_plugin):
    root = Path(os.environ.get('RVW_HDL_REF', Path(__file__).parents[3] / 'ref')) / 'neorv32'
    listing = root / 'rtl/file_list_core.f'
    if not listing.exists():
        pytest.skip('neorv32 read-only reference checkout is absent; set RVW_HDL_REF')
    sources = [Path(line.strip().replace('$NEORV32_HOME', str(root))) for line in listing.read_text().split()
               if line.strip()]
    out = tmp_path / 'cpu.db'
    build_hdl(sources, 'neorv32_cpu', out, yosys=YOSYS, frontend='ghdl', library='neorv32', timeout=300)
    db = DesignDB(out)
    try:
        names = {c['name']: c['module'] for c in ops.hierarchy(db, depth=1)['root']['children']}
        assert names['cpu_regfile_inst'] == 'neorv32_cpu_regfile' and 'cpu_control_inst' in names
        assert ops.where(db, 'cpu_regfile_inst.rf_we')['signal']['loc'].endswith('neorv32_cpu_regfile.vhd:53')
        assert db.q("SELECT count(*) FROM memories")[0][0] >= 1
        pc = db.resolve_one('cpu_control_inst.ctrl_o[pc_cur]')
        cd = db.clock_domain(pc.clock_domain_id)
        assert pc.kind == 'reg' and cd['reset'] == 'rstn_i' and cd['reset_active'] == 'low'
        assert ops.path(db, 'ibus_rsp_i[data]', 'cpu_regfile_inst.rd_we_i')['found']
    finally:
        db.close()


@needs_ghdl
def test_neorv32_uart(tmp_path, memory_plugin):
    """A second real VHDL design, with FIFO memories and top generics."""
    from rvw.common.proc import run_group
    from rvw.query.hdl_ghdl import ghdl_prefix, plugin_path
    from test_query_slang import _oracle
    root = Path(os.environ.get('RVW_HDL_REF', Path(__file__).parents[3] / 'ref')) / 'neorv32'
    listing = root / 'rtl/file_list_core.f'
    if not listing.exists():
        pytest.skip('NEORV32 external reference is absent')
    sources = [Path(line.replace('$NEORV32_HOME', str(root))) for line in listing.read_text().split()]
    out = tmp_path / 'uart.db'
    build_hdl(sources, 'neorv32_uart', out, yosys=YOSYS, frontend='ghdl', library='neorv32',
              parameters=['RX_FIFO_DEPTH=4', 'TX_FIFO_DEPTH=4'])
    netlist, script = tmp_path / 'oracle.json', tmp_path / 'oracle.ys'
    script.write_text('ghdl --std=08 --work=neorv32 -gRX_FIFO_DEPTH=4 -gTX_FIFO_DEPTH=4 '
                      + ' '.join(map(str, sources)) + f' -e neorv32_uart\nwrite_json {netlist}\n')
    tool = type('Tool', (), {'resolved': os.path.realpath(YOSYS)})()
    env = {**os.environ, 'GHDL_PREFIX': ghdl_prefix(tool) or ''}
    p = run_group([YOSYS, '-Q', '-T', '-m', str(plugin_path(tool, None)), '-s', str(script)],
                  cwd=tmp_path, env=env, capture=True, timeout=90)
    assert p.returncode == 0, p.stderr
    oracle = _oracle(netlist, 'neorv32_uart')
    db = DesignDB(out)
    try:
        assert ops.where(db, 'uart_rxd_i')['signal']['loc'].endswith('neorv32_uart.vhd:36')
        assert db.q('SELECT count(*) FROM memories')[0][0] == 2
        for a in ('uart_rxd_i', 'uart_ctsn_i', 'bus_req_i[data]', 'clkgen_i'):
            for b in ('uart_txd_o', 'uart_rtsn_o', 'irq_o', 'bus_rsp_o[data]'):
                assert ops.path(db, a, b)['found'] == oracle(a, b), (a, b)
    finally:
        db.close()
