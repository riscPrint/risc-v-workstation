"""Clock inference and synchronizer classes on small exact-schema graphs."""
import pytest
from lint_builder import Builder
from rvw.lint import structural
from rvw.query.db import run_on


def analyze(db, intent=None):
    return run_on(db, lambda d: structural.analyze(d, intent or {}))


def rules(r):
    return [f['rule'] for f in r['findings']]


def kinds(r):
    return {c['destination']: c['kind'] for c in r['crossings']}


def two_clocks(tmp_path):
    b = Builder(tmp_path / 'd.db')
    b.domain(1, clock='clkA')
    b.domain(2, clock='clkB')
    b.sig('clkA', direction='in', role='clock')
    b.sig('clkB', direction='in', role='clock')
    return b


def test_buffer_cc_library_and_three_stages(tmp_path):
    b = two_clocks(tmp_path)
    b.reg('src', 1)
    b.component('cc', 'spinal.lib.BufferCC')
    b.sig('cc.io_dataIn', direction='in', comp='cc')
    for i in range(3):
        b.reg(f'cc.buf{i}', 2, comp='cc', tags='tag spinal.core.crossClockDomain$:x' if i == 0 else None)
    b.chain('src', 'cc.io_dataIn', 'cc.buf0', 'cc.buf1', 'cc.buf2')
    r = analyze(b.done())
    row = r['crossings'][0]
    assert row['kind'] == 'sync_3ff' and row['library']['kind'] == 'buffer_cc'
    assert row['stages'] == ['cc.buf0', 'cc.buf1', 'cc.buf2']
    assert rules(r) == ['cdc.sync_candidate']
    assert r['cdc']['hierarchy'][0]['component'] == 'cc'
    assert {c['kind'] for c in r['cdc']['clocks']} == {'primary'}
    assert row['relationship'] == 'asynchronous'


@pytest.mark.parametrize('fault,rule', [('logic', 'cdc.comb_before_sync'), ('fanout', 'cdc.sync_stage_fanout'),
                                         ('copies', 'cdc.fanout_before_sync')])
def test_synchronizer_faults(tmp_path, fault, rule):
    b = two_clocks(tmp_path)
    b.reg('src', 1)
    b.reg('s0', 2, tags='tag spinal.core.crossClockDomain$:x')
    b.reg('s1', 2)
    b.edge('s0', 's1')
    if fault == 'logic':
        b.reg('src2', 1)
        b.sig('mix')
        b.chain('src', 'mix', 's0')
        b.edge('src2', 'mix')
    else:
        b.edge('src', 's0')
    if fault == 'fanout':
        b.reg('use', 2)
        b.edge('s0', 'use')
    if fault == 'copies':
        b.reg('t0', 2)
        b.reg('t1', 2)
        b.chain('src', 't0', 't1')
    r = analyze(b.done())
    assert rule in rules(r)
    severity = {f['rule']: f['severity'] for f in r['findings']}
    assert severity[rule] == ('warning' if fault == 'copies' else 'error')


def test_gray_bus_emits_obligation(tmp_path):
    b = two_clocks(tmp_path)
    b.reg('bin', 1, width=3, type_='UInt')
    b.reg('gray', 1, width=3)
    b.edge('bin', 'gray')
    key = (' := CastUIntToBits[3](Operator$UInt$Xor[3](bin:UInt[3],'
           'Operator$UInt$ShiftRightByIntFixedWidth<1>[3](bin:UInt[3])))')
    b.assign('gray', key)
    b.reg('g0', 2, width=3)
    b.reg('g1', 2, width=3)
    b.chain('gray', 'g0', 'g1')
    db = b.done()
    r = analyze(db)
    assert kinds(r)['g0'] == 'gray_sync'
    ob = r['cdc']['obligations'][0]
    assert ob['kind'] == 'gray_code' and ob['signal'] == 'gray' and ob['width'] == 3


def test_binary_bus_through_two_stages_is_multi_bit(tmp_path):
    b = two_clocks(tmp_path)
    b.reg('bin', 1, width=3)
    b.reg('g0', 2, width=3)
    b.reg('g1', 2, width=3)
    b.chain('bin', 'g0', 'g1')
    r = analyze(b.done())
    assert kinds(r)['g0'] == 'multi_bit' and rules(r) == ['cdc.multi_bit']


def test_qualified_data(tmp_path):
    b = two_clocks(tmp_path)
    b.reg('req', 1)
    b.reg('data', 1, width=8)
    b.reg('r0', 2)
    b.reg('r1', 2)
    b.chain('req', 'r0', 'r1')
    b.reg('capture', 2, width=8)
    b.edge('data', 'capture')
    b.edge('r1', 'capture', 'cond')
    r = analyze(b.done())
    assert kinds(r)['capture'] == 'qualified_data'
    ob = next(o for o in r['cdc']['obligations'] if o['kind'] == 'data_stable')
    assert ob['signal'] == 'data' and ob['qualifier'] == 'req'


def test_clock_inference_and_related_paths(tmp_path):
    b = Builder(tmp_path / 'd.db')
    b.domain(1, clock='clk')
    b.domain(2, clock='div')
    b.domain(3, clock='gclk')
    b.domain(4, clock='pll.out')
    b.sig('clk', direction='in', role='clock')
    b.sig('en', direction='in')
    b.reg('div', 1)
    b.edge('div', 'div')
    b.sig('gclk', role='clock')
    b.chain('clk', 'gclk')
    b.edge('en', 'gclk')
    b.component('pll', 'Pll')
    b.c.execute("UPDATE components SET blackbox=1 WHERE path='pll'")
    b.sig('pll.out', direction='out', comp='pll')
    b.reg('a', 1)
    b.reg('d', 2)
    b.reg('g', 3)
    b.reg('p', 4)
    b.chain('a', 'd')
    b.chain('a', 'g')
    b.chain('a', 'p')
    r = analyze(b.done())
    info = {c['clock']: c for c in r['cdc']['clocks']}
    assert info['clk']['kind'] == 'primary'
    assert info['div']['kind'] == 'divided' and info['div']['divide_by'] == 2 and info['div']['master'] == 'clk'
    assert info['gclk']['kind'] == 'gated' and info['gclk']['enables'] == ['en'] and info['gclk']['master'] == 'clk'
    assert info['pll.out']['kind'] == 'generated' and info['pll.out']['master'] is None
    k = kinds(r)
    assert k['d'] == k['g'] == 'synchronous_related'
    assert k['p'] == 'unsynchronized'
    assert next(c for c in r['crossings'] if c['destination'] == 'p')['relationship'] == 'unknown'


def test_declared_clock_groups(tmp_path):
    b = two_clocks(tmp_path)
    b.reg('src', 1)
    b.reg('dst', 2)
    b.edge('src', 'dst')
    db = b.done()
    group = dict(clocks=['clkA', 'clkB'], relationship='synchronous', reason='same PLL output, phase aligned')
    r = analyze(db, {'clocks': [group]})
    assert r['crossings'][0]['relationship'] == 'declared_synchronous'
    assert rules(r) == ['cdc.related_clock_crossing']
    with pytest.raises(ValueError, match='unknown clock'):
        analyze(db, {'clocks': [dict(group, clocks=['clkA', 'nope'])]})
    with pytest.raises(ValueError, match='reason'):
        analyze(db, {'clocks': [dict(group, reason='')]})


@pytest.mark.parametrize('library', [True, False])
def test_memory_crossing(tmp_path, library):
    b = two_clocks(tmp_path)
    if library:
        b.component('fifo', 'spinal.lib.StreamFifoCC')
    comp = 'fifo' if library else ''
    m = b.sig('fifo.ram' if library else 'ram', kind='mem', width=8, comp=comp)
    b.reg('x', 1)
    b.c.execute("INSERT INTO memories(id,signal_id,component_id,name,path,width,depth) VALUES(1,?,?,'ram','ram',8,4)",
                (m, b.comps[comp]))
    b.c.execute("INSERT INTO mem_ports(id,memory_id,kind,clock_domain_id) VALUES(1,1,'write',1)")
    b.c.execute("INSERT INTO mem_ports(id,memory_id,kind,clock_domain_id) VALUES(2,1,'read_sync',2)")
    r = analyze(b.done())
    assert rules(r) == (['cdc.async_fifo_candidate'] if library else ['cdc.memory_crossing'])
    assert r['cdc']['memories'][0]['domains'] == [[1, 2]]


def gray_design(tmp_path):
    b = two_clocks(tmp_path)
    b.c.execute("UPDATE components SET module='Top' WHERE id=1")
    b.reg('bin', 1, width=3, type_='UInt')
    b.reg('gray', 1, width=3)
    b.edge('bin', 'gray')
    b.assign('gray', ' := CastUIntToBits[3](Operator$UInt$Xor[3](bin:UInt[3],'
                     'Operator$UInt$ShiftRightByIntFixedWidth<1>[3](bin:UInt[3])))')
    b.reg('g0', 2, width=3)
    b.reg('g1', 2, width=3)
    b.chain('gray', 'g0', 'g1')
    return b.done()


RTL = '''module Top(input clkA, input clkB, output reg [2:0] g1);
  reg [2:0] bin = 0, gray = 0, g0 = 0;
  always @(posedge clkA) begin bin <= bin + 1; gray <= bin ^ (bin >> 1); end
  always @(posedge clkB) begin g0 <= gray; g1 <= g0; end
endmodule
'''


def test_emit_checks_and_checked_rtl(tmp_path, capsys):
    import json, shutil, subprocess
    from rvw.cli import main
    db = gray_design(tmp_path)
    rtl = tmp_path / 'Top.v'
    rtl.write_text(RTL)
    settings = tmp_path / 'lint.json'
    settings.write_text(json.dumps(dict(schema='rvw.lint-settings/1', config='c', top='Top', db=str(db),
                                        files=[str(rtl)], backends=['structural'])))
    out = tmp_path / 'emit'
    assert main(['lint', '--settings', str(settings), '--emit', str(out), '--json']) == 1
    r = json.loads(capsys.readouterr().out)
    assert r['emitted']['bound'] == 1
    manifest = json.loads((out / 'cdc_obligations.json').read_text())
    ob = manifest['obligations'][0]
    assert ob['bind']['ports'] == {'clk': 'clkA', 'value': 'gray'} and ob['placed']
    assert 'bind Top rvw_cdc_gray #(.W(3)) rvw_gray_0 (.clk(clkA), .value(gray));' in (out / 'cdc_checks.sv').read_text()
    checked = (out / 'checked/Top.v').read_text()
    assert 'rvw_cdc_gray #(.W(3)) rvw_gray_0' in checked
    assert main(['lint', '--settings', str(settings), '--emit', str(out)]) == 2
    if shutil.which('yosys'):
        script = (f'read_verilog -formal -sv {out}/checked/Top.v {out}/checked/rvw_cdc_checkers.sv; '
                  'hierarchy -top Top; proc; flatten; select -assert-any t:$check t:$assert')
        assert subprocess.run(['yosys', '-q', '-p', script], capture_output=True).returncode == 0


def test_spinal_synchronous_tag(tmp_path):
    b = two_clocks(tmp_path)
    tag = 'tag spinal.core.ClockSyncTag:spinal.core.ClockSyncTag(a=signal clkA,b=signal clkB)'
    b.c.execute('UPDATE signals SET tags=? WHERE path IN (\'clkA\',\'clkB\')', (tag,))
    b.reg('src', 1)
    b.reg('dst', 2)
    b.edge('src', 'dst')
    r = analyze(b.done())
    assert r['crossings'][0]['relationship'] == 'declared_synchronous'
    assert rules(r) == ['cdc.related_clock_crossing']


def test_toggle_qualified_data(tmp_path):
    b = two_clocks(tmp_path)
    b.reg('req', 1)
    b.edge('req', 'req')                      # toggles itself
    b.reg('data', 1, width=8)
    b.reg('r0', 2)
    b.reg('r1', 2)
    b.chain('req', 'r0', 'r1')
    b.reg('capture', 2, width=8)
    b.edge('data', 'capture')
    b.edge('r1', 'capture', 'cond')
    r = analyze(b.done())
    ob = next(o for o in r['cdc']['obligations'] if o['signal'] == 'data')
    assert ob['kind'] == 'toggle_stable' and ob['qualifier'] == 'req'


@pytest.mark.fast
@pytest.mark.parametrize('width', [1, 8])
def test_toggle_payload_tag_is_not_a_synchronizer_stage(tmp_path, width):
    b = two_clocks(tmp_path)
    b.component('bridge', 'spinal.lib.FlowCCUnsafeByToggle')
    b.reg('bridge.data', 1, width=width, comp='bridge')
    b.reg('bridge.req', 1, comp='bridge'); b.edge('bridge.req', 'bridge.req')
    b.reg('s0', 2); b.reg('s1', 2)
    b.chain('bridge.req', 's0', 's1')
    b.reg('capture', 2, width=width, tags='crossClockDomain')
    b.edge('bridge.data', 'capture'); b.edge('s1', 'capture', 'cond')
    r = analyze(b.done())
    row = next(c for c in r['crossings'] if c['source'] == 'bridge.data')
    assert row['kind'] == 'qualified_data'
    assert not [f for f in r['findings'] if f['rule'] == 'cdc.comb_before_sync']
    assert any(o['signal'] == 'bridge.data' for o in r['cdc']['obligations'])
