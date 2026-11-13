"""Fast tests of the burst bus model and cache observations. No simulator is needed."""
import json
import pytest
from rvw.sec import core_adapter, rtl

pytestmark = pytest.mark.fast

VERILOG = """module Core (
  output wire          dbus_valid,
  input  wire          dbus_ready,
  output wire [31:0]   dbus_addr,
  output wire          dbus_wr,
  output wire [2:0]    dbus_size,
  input  wire          dbus_rsp,
  input  wire          dbus_last,
  input  wire [31:0]   dbus_data,
  input  wire          clk,
  input  wire          reset
);
endmodule
"""


def binding(tmp_path, burst=True):
    (tmp_path/'core.v').write_text(VERILOG)
    bus = dict(name='dbus', kind='data', burst=burst, write_response=False, cmd_valid='dbus_valid',
               cmd_ready='dbus_ready', cmd_address='dbus_addr', cmd_write='dbus_wr', cmd_size='dbus_size',
               rsp_valid='dbus_rsp', rsp_data='dbus_data', rsp_last='dbus_last')
    b = dict(schema=rtl.SCHEMA, name='core', rtl=['core.v'], top='Core', clock='clk', reset='reset',
             ram=dict(base='0x80000000', size='0x1000'), retire=dict(kind='rvfi'), buses=[bus])
    (tmp_path/'core.json').write_text(json.dumps(b))
    return rtl.load(tmp_path/'core.json')


def test_burst_read_queues_one_beat_per_word_of_the_aligned_line(tmp_path):
    b = binding(tmp_path)
    tb = rtl.testbench(b, rtl.ports(b))
    assert 'dbus_beats = dbus_wr ? 1 : ((1 << dbus_size) > 4 ? (1 << dbus_size) / 4 : 1);' in tb
    assert "dbus_a = (dbus_beats > 1 ? (dbus_addr & ~((32'd1 << dbus_size) - 1)) : dbus_addr) + 4*dbus_k;" in tb
    assert 'dbus_q_last[dbus_tail % 64] = dbus_k == dbus_beats - 1;' in tb
    assert 'dbus_last = dbus_q_last[dbus_head % 64];' in tb and 'dbus_last = 0;' in tb


def test_single_beat_bus_keeps_the_short_queue(tmp_path):
    b = binding(tmp_path, burst=False)
    tb = rtl.testbench(b, rtl.ports(b))
    assert 'dbus_beats' not in tb and 'dbus_q_data[dbus_tail % 16]' in tb


def test_cache_events_drop_line_contents():
    sites = [dict(id=0, kind='cache', name='icache_fill', valid='v', fields=[['address', 32, 'a'], ['data', 256, 'd']]),
             dict(id=1, kind='branch', name='bp', valid='w', fields=[['pc', 32, 'p'], ['data', 32, 'q']])]
    rows = [(3, 0, [0x80000000, 0x1234]), (4, 1, [0x80000004, 7])]
    result = dict(retired=[dict(cycle=2, pc=1), dict(cycle=6, pc=2)], bus=[], probe_sites=sites, probe_rows=rows,
                  done=-1, tohost_address=0)
    obs = core_adapter.observe(result, ['cache_events', 'probe_events'])
    assert obs['cache_events'] == [dict(cycle=3, kind='cache', name='icache_fill', address=0x80000000)]
    # Only cache contents are removed; other probe fields stay.
    assert obs['probe_events'][1]['data'] == 7 and 'data' not in obs['probe_events'][0]


def test_commit_port_with_mode_records_the_privilege(tmp_path):
    b = binding(tmp_path)
    b['retire'] = dict(kind='commit', valid='c_valid', pc='c_pc', mode='c_priv')
    tb = rtl.testbench(b, rtl.ports(b))
    assert '$fdisplay(fd, "C %0d %h %0d", cycle, dut.c_pc, dut.c_priv);' in tb
    image = bytearray(16); image[4:8] = (0x13).to_bytes(4, 'little')
    parsed = rtl.parse('C 5 80000004 0\nC 6 80000008\n', bytes(image), b)
    assert parsed['retired'][0] == dict(cycle=5, pc=0x80000004, insn=0x13, mode=0)
    assert 'mode' not in parsed['retired'][1]
