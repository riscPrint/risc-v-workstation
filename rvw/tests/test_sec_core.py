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
    b = dict(schema=rtl.SCHEMA, name='core', rtl=['core.v'], top='Core', clock='clk', reset='reset',
             ram=dict(base='0x80000000', size='0x1000'),
             buses=[dict(name='ibus', kind='fetch', cmd_valid='ibus_valid', cmd_ready='ibus_ready',
                         cmd_address='ibus_addr', rsp_valid='ibus_rsp', rsp_data='ibus_data')],
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
