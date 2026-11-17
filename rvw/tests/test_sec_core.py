"""Fast tests of the native core harness pieces. No simulator or compiler is needed."""
import json
import pytest
from rvw.sec import core_adapter, ift_core, pairs, rtl

pytestmark = pytest.mark.fast

VERILOG = """module Core (
  output wire          ibus_valid,
  input  wire          ibus_ready,
  output wire [31:0]   ibus_addr,
  input  wire          ibus_rsp,
  input  wire [31:0]   ibus_data,
  input  wire          irq,
  output wire [1:0]    rvfi_mode,
  input  wire          clk,
  input  wire          reset
);
endmodule
"""


def binding(tmp_path, **extra):
    (tmp_path/'core.v').write_text(VERILOG)
    extra.setdefault('buses', [dict(name='ibus', kind='fetch', cmd_valid='ibus_valid', cmd_ready='ibus_ready',
                                    cmd_address='ibus_addr', rsp_valid='ibus_rsp', rsp_data='ibus_data')])
    b = dict(schema=rtl.SCHEMA, name='core', rtl=['core.v'], top='Core', clock='clk', reset='reset',
             ram=dict(base='0x80000000', size='0x1000'),
             retire=dict(kind='rvfi'), **extra)
    (tmp_path/'core.json').write_text(json.dumps(b))
    return rtl.load(tmp_path/'core.json')


def test_binding_and_ports(tmp_path):
    b = binding(tmp_path)
    assert b['ram_base'] == 0x80000000 and b['rtl'][0] == tmp_path/'core.v'
    assert rtl.ports(b)['ibus_addr'] == ('output', 32) and rtl.ports(b)['irq'] == ('input', 1)
    bad = json.loads((tmp_path/'core.json').read_text()); bad['retire'] = {'kind': 'guess'}
    (tmp_path/'bad.json').write_text(json.dumps(bad))
    with pytest.raises(ValueError, match='retire kind'):
        rtl.load(tmp_path/'bad.json')


def test_unset_environment_path_is_an_error(tmp_path, monkeypatch):
    b = json.loads(json.dumps(dict(schema=rtl.SCHEMA, rtl=['${RVW_NO_SUCH_VAR}/x.v'])))
    (tmp_path/'core.json').write_text(json.dumps(b))
    monkeypatch.delenv('RVW_NO_SUCH_VAR', raising=False)
    with pytest.raises(ValueError, match='unset environment'):
        rtl.load(tmp_path/'core.json')


def test_testbench_ties_inputs_and_answers_in_order(tmp_path):
    b = binding(tmp_path)
    tb = rtl.testbench(b, rtl.ports(b))
    assert "irq = 1'd0;" in tb and 'ibus_ready = 1;' in tb
    assert 'ibus_q_data[ibus_tail % 16] = inram(ibus_addr)' in tb  # data read at acceptance
    assert '$fdisplay(fd, "B %0d ibus' in tb
    shadow = rtl.testbench(b, rtl.ports(b), ift=('_', [('ibus_addr', 'ibus_valid')]))
    assert 'Core__ift dut' in shadow and '(|ibus_addr__t) && (ibus_valid || (|ibus_valid__t))' in shadow


def test_same_cycle_bus_reads_in_drive_and_queues_nothing(tmp_path):
    b = binding(tmp_path, buses=[dict(name='ibus', kind='fetch', latency=0, cmd_valid='ibus_valid',
                                      cmd_address='ibus_addr', rsp_data='ibus_data')])
    tb = rtl.testbench(b, rtl.ports(b))
    drive = tb[tb.index('task automatic drive;'):tb.index('endtask')]
    assert 'ibus_data = (ibus_valid && inram(ibus_addr)) ? mem[' in drive
    assert 'ibus_tail = ibus_tail + 1' not in tb and 'ibus_head = ibus_head + 1' not in tb
    assert 'if (ibus_valid) $fdisplay(fd, "A %0d ibus"' in tb
    shadow = rtl.testbench(b, rtl.ports(b), ift=('_', [('ibus_addr', 'ibus_valid')]))
    assert 'ibus_data__t = (ibus_valid && inram(ibus_addr)) ? taint[' in shadow
    (tmp_path/'core.json').write_text(json.dumps(dict(json.loads((tmp_path/'core.json').read_text()),
        buses=[dict(name='ibus', kind='fetch', cmd_valid='ibus_valid', cmd_address='ibus_addr', rsp_data='ibus_data')])))
    with pytest.raises(ValueError, match='rsp_valid'):
        rtl.load(tmp_path/'core.json')


def rows():
    return [dict(cycle=10, pc=0x80000000, pc_next=0x80000004, insn=0x13, trap=0, mode=0, rd=0, rd_wdata=5,
                 mem_addr=4, mem_rmask=0, mem_wmask=0, mem_wdata=0, mem_rdata=0),
            dict(cycle=20, pc=0x80000100, pc_next=0x80000104, insn=0x13, trap=0, mode=3, rd=1, rd_wdata=7,
                 mem_addr=0, mem_rmask=0, mem_wmask=0, mem_wdata=0, mem_rdata=0),
            dict(cycle=25, pc=0x80000104, pc_next=0x80000108, insn=0x23, trap=0, mode=3, rd=0, rd_wdata=0,
                 mem_addr=0x80000800, mem_rmask=0, mem_wmask=15, mem_wdata=1, mem_rdata=0),
            dict(cycle=26, pc=0x80000108, pc_next=0x80000108, insn=0x6f, trap=0, mode=3, rd=0, rd_wdata=0,
                 mem_addr=0, mem_rmask=0, mem_wmask=0, mem_wdata=0, mem_rdata=0)]


def test_c2_synthesizes_trapped_instruction_and_cuts_at_tohost(tmp_path):
    b = binding(tmp_path)
    image = bytearray(0x1000); image[4:8] = (0x73).to_bytes(4, 'little')
    result = dict(retired=rows(), traps=[dict(cycle=12, cause=8, tval=0)], privilege=[(5, 0), (12, 3)],
                  bus=[], sinks=[], cycles=30, done=24, tohost=1, tohost_address=0x80000800, image=bytes(image))
    assert rtl.c2(result, tmp_path/'c2.jsonl', 'x.elf', b, 'rv32i') == 'pass'
    lines = [json.loads(x) for x in (tmp_path/'c2.jsonl').read_text().splitlines()]
    records = [x for x in lines[1:] if 'event' not in x]
    assert [x['pc'] for x in records] == ['0x80000000', '0x80000004', '0x80000100', '0x80000104']
    trapped = records[1]
    assert trapped['trap'] is True and trapped['insn'] == '0x73' and trapped['mode'] == 0
    assert records[0]['mem_addr'] == '0x0'  # no access: normalized like Spike
    assert any(x.get('event') == 'trap' for x in lines) and lines[-1]['status'] == 'pass'
    assert list(pairs.trace(tmp_path/'c2.jsonl'))  # the C2 reader accepts it


def test_observation_window_and_observer_mode():
    result = dict(retired=rows(), bus=[dict(cycle=21, bus='dbus', address=8, write=False),
                                       dict(cycle=40, bus='dbus', address=9, write=True)],
                  done=24, tohost_address=0x80000800)
    obs = core_adapter.observe(result, ['cycles', 'retire_cycles', 'dbus_trace', 'dbus_addresses'], '0x80000100')
    assert obs == dict(cycles=5, retire_cycles=[5], dbus_trace=[[1, 8, False]], dbus_addresses=[[8, False]])
    user = core_adapter.observe(result, ['retire_cycles'], None, mode=0)
    assert user == dict(retire_cycles=[])
    with pytest.raises(ValueError, match='unknown observation'):
        core_adapter.observe(result, ['power'])
    with pytest.raises(ValueError, match='not retired'):
        core_adapter.observe(result, ['cycles'], '0x1234')


def test_render_uses_fixed_length_setup(tmp_path):
    t = tmp_path/'t.S'; t.write_text('# RVW_SETUP\n# RVW_PROGRAM\n# RVW_DATA\n')
    small = core_adapter.render(t, dict(secret={'x6': 1, '@key': [1, 2]}, program=['add x1, x2, x3']))
    large = core_adapter.render(t, dict(secret={'x6': 0x7fffffff, '@key': [3, 4]}, program=['add x1, x2, x3']))
    count = lambda text: sum(1 for x in text.splitlines() if x.strip().startswith(('lui', 'addi')))
    assert count(small) == count(large) == 2
    assert 'key:' in small and '.word 1' in small
    # lui/addi rebuilds the value, including negative low parts.
    for v in (0, 1, 0x7ff, 0x800, 0xfffff800, 0x7fffffff, 0xffffffff):
        hi = (v + 0x800) >> 12 & 0xfffff; lo = (v & 0xfff) - ((v & 0x800) << 1)
        assert ((hi << 12) + lo) & 0xffffffff == v
    with pytest.raises(ValueError, match='secret must map'):
        core_adapter.render(t, dict(secret=3, program=[]))


def test_observer_mode_limits_the_contract():
    ref = lambda m: [dict(pc=1, mode=3, mem_addr=0, mem_rmask=0, mem_wmask=0, insn=0x13),
                     dict(pc=m, mode=3, mem_addr=0, mem_rmask=0, mem_wmask=0, insn=0x13),
                     dict(pc=9, mode=0, mem_addr=0, mem_rmask=0, mem_wmask=0, insn=0x13)]
    a = dict(public={}, secret=1, reference=ref(2), observations=dict(t=[1]))
    b = dict(public={}, secret=2, reference=ref(3), observations=dict(t=[2]))
    plan = dict(contract='sandboxing', clauses=['pc'], observations=['t'])
    assert pairs.compare(a, b, plan)['status'] == 'ineligible'
    assert pairs.compare(a, b, dict(plan, observer_mode=0)) == dict(status='violation', channels=['t'])


PROBED = """module Core (
  input  wire          clk,
  input  wire          reset
);
  wire                rvwprobe__branch__bp__valid;
  wire       [31:0]   rvwprobe__branch__bp__pc;
  wire                rvwprobe__branch__bp__taken;
  wire                rvwprobe__interrupt__irq__valid_1;
  wire                rvwprobe__counter__cycles__valid;
  wire       [7:0]    rvwprobe__counter__cycles__inc;
  wire                rvwprobe__stage__D__valid;
endmodule
"""


def test_probe_sites_stream_and_channels(tmp_path):
    from rvw.sec import probe_events
    from rvw.probes.events import read
    (tmp_path/'core.v').write_text(PROBED)
    b = dict(rtl=[tmp_path/'core.v'], top='Core', probe_meta={'branch:bp': {'semantics': 'final-prediction'}},
             events=[dict(kind='cache', name='l1', valid='hit_valid', fields={'address': ['hit_addr', 32]})])
    sites = probe_events.discover(b)
    assert [(s['kind'], s['name']) for s in sites] == [('branch', 'bp'), ('counter', 'cycles'), ('cache', 'l1')]
    assert sites[0]['fields'] == [['pc', 32, 'rvwprobe__branch__bp__pc'], ['taken', 1, 'rvwprobe__branch__bp__taken']]
    assert 'if (dut.rvwprobe__branch__bp__valid) $fdisplay(fd, "Q %0d 0 %0d %0d", cycle, dut.rvwprobe__branch__bp__pc' \
        in probe_events.testbench_lines(sites)[0]
    rows = [(3, 0, [0x80000000, 1]), (3, 1, [2]), (4, 1, [5]), (5, 2, [0x80000040])]
    probe_events.write(tmp_path/'p.jsonl', sites, rows, 6, dict(core='c', config='x', elf='e'))
    stream = read(tmp_path/'p.jsonl')
    assert stream.end['counters'] == {'cycles': 7} and stream.probes[0].meta['semantics'] == 'final-prediction'
    result = dict(retired=[dict(cycle=2, pc=1), dict(cycle=6, pc=2)], bus=[dict(cycle=3, bus='dbus', address=4, write=False)],
                  responses=[dict(cycle=4, bus='dbus')], probe_sites=sites, probe_rows=rows, done=-1, tohost_address=0)
    obs = core_adapter.observe(result, ['branch_events', 'cache_events', 'probe_counters', 'bus_handshakes'])
    assert obs['branch_events'] == [dict(cycle=3, kind='branch', name='bp', pc=0x80000000, taken=1)]
    assert obs['cache_events'][0]['address'] == 0x80000040 and obs['probe_counters'] == {'cycles': 7}
    assert obs['bus_handshakes'] == [[3, 'dbus', 'cmd'], [4, 'dbus', 'rsp']]
    with pytest.raises(ValueError, match='needs probe sites'):
        core_adapter.observe(dict(result, probe_sites=[]), ['tlb_events'])


def test_simulation_identity_tracks_executable_not_mutable_sources(tmp_path, monkeypatch):
    import hashlib
    b = binding(tmp_path)
    exe = tmp_path/'simulator'
    exe.write_bytes(b'compiled model A')
    monkeypatch.setattr(rtl, 'image', lambda *a: (bytearray(16), 8, 0))
    monkeypatch.setattr(rtl, 'native', lambda *a, **kw: None)
    monkeypatch.setattr(rtl, 'parse', lambda *a: dict(cycles=1))
    out = tmp_path/'run'; out.mkdir(); (out/'sim.log').write_text('')
    first = rtl.simulate(b, exe, 'case.elf', out, taint_words={1: 1})
    (tmp_path/'core.v').write_text('changed source after compilation')
    second = rtl.simulate(b, exe, 'case.elf', out, taint_words={1: 1})
    assert first['rtl_identity'] == second['rtl_identity'] == hashlib.sha256(exe.read_bytes()).hexdigest()
    exe.write_bytes(b'compiled model B')
    third = rtl.simulate(b, exe, 'case.elf', out, taint_words={1: 1})
    assert third['rtl_identity'] != first['rtl_identity']
