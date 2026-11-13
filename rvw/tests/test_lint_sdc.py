"""SDC generation and checks on small exact-schema graphs. Logical intent only."""
import json
import pytest
from lint_builder import Builder
from rvw.lint import sdc
from rvw.lint.cli import report
from rvw.query.db import run_on


def design(tmp_path, unsafe=False):
    b = Builder(tmp_path / 'd.db')
    b.domain(1, clock='clkA')
    b.domain(2, clock='clkB')
    b.domain(3, clock='div')
    b.sig('clkA', direction='in', role='clock')
    b.sig('clkB', direction='in', role='clock')
    b.sig('rst', direction='in')
    b.reg('div', 1)
    b.edge('div', 'div')
    b.reg('src', 1)
    b.reg('s0', 2, tags='tag spinal.core.crossClockDomain$:x; tag spinal.core.crossClockMaxDelay:'
                        'spinal.core.crossClockMaxDelay(cycles=Int(2),useTargetClock=Boolean(true))')
    b.reg('s1', 2, tags='tag spinal.core.crossClockFalsePath:spinal.core.crossClockFalsePath('
                        'destType=spinal.core.TimingEndpointType$RESET$,source=scala.Some(value=signal rst))')
    b.chain('src', 's0', 's1')
    b.reg('slow', 3)
    b.edge('src', 'slow')
    b.reg('m0', 1)
    b.reg('m1', 1)
    b.edge('m0', 'm1')
    if unsafe:
        b.reg('bus', 1, width=8)
        b.reg('busB', 2, width=8)
        b.edge('bus', 'busB')
    return b.done()


def run(db, cfg, intent=None):
    return run_on(db, lambda d: sdc.analyze(d, cfg, intent or {}))


CLOCKS = {'clocks': {'clkA': {'period_ns': 10}, 'clkB': {'period_ns': 4}}}


def test_generation(tmp_path):
    cfg = dict(CLOCKS, multicycle=[dict(**{'from': 'm0'}, to='m1', setup=2, reason='enable every 2nd cycle')])
    r = run(design(tmp_path), cfg)
    text = r['sdc']
    assert 'create_clock -name clkA -period 10 [get_ports {clkA}]' in text
    assert 'create_generated_clock -name div -source [get_ports {clkA}] -divide_by 2 [get_pins {div_reg*/Q}]' in text
    assert 'set_max_delay -datapath_only 8 -from [get_cells {src_reg*}] -to [get_cells {s0_reg*}]' in text
    assert 'set_false_path -from [get_ports {rst}] -to [get_cells {s1_reg*}]' in text
    assert 'set_multicycle_path 2 -setup -from [get_cells {m0_reg*}] -to [get_cells {m1_reg*}]' in text
    assert 'set_multicycle_path 1 -hold' in text
    assert 'slow_reg' not in text  # related clocks need no exception
    assert r['findings'] == []


def test_generation_findings(tmp_path):
    db = design(tmp_path, unsafe=True)
    cfg = {'clocks': {'clkA': {'period_ns': 10}},
           'multicycle': [dict(**{'from': 's1'}, to='m1', setup=3, reason='wrong')]}
    rules = {f['rule'] for f in run(db, cfg)['findings']}
    assert rules == {'sdc.unconstrained_clock', 'sdc.unsafe_crossing', 'sdc.unmatched_multicycle',
                     'sdc.unresolved_max_delay'}
    for bad in ({'clocks': {'clkA': {'period_ns': 0}}}, {'nope': 1}, {'clocks': {'zz': {'period_ns': 1}}},
                {'multicycle': [{'from': 'a', 'to': 'b', 'setup': 1, 'reason': 'x'}]}):
        with pytest.raises(ValueError):
            run(db, bad)


SDC_GOOD = '''create_clock -name clkA -period 10 [get_ports {clkA}]
create_clock -name clkB -period 4 [get_ports clkB]
create_generated_clock -name div -source [get_ports clkA] -divide_by 2 [get_pins {div_reg/Q}]
set_max_delay -datapath_only 8 -from [get_cells {src_reg*}] -to [get_cells {s0_reg*}]
'''


def test_check_good_and_bad(tmp_path):
    db = design(tmp_path, unsafe=True)
    good = tmp_path / 'good.sdc'
    good.write_text(SDC_GOOD + 'set_false_path -from [get_clocks clkA] -to [get_cells {busB_reg*}]\n')
    r = run(db, dict(CLOCKS, check=str(good)))
    rules = {f['rule'] for f in r['findings']}
    assert 'sdc.unsafe_false_path' in rules
    assert 'sdc.unconstrained_crossing' not in rules and 'sdc.unmatched_clock' not in rules
    assert r['check']['covered_crossings'] == 2
    bad = tmp_path / 'bad.sdc'
    bad.write_text('create_clock -name ghost -period 5 [get_ports {nothere}]\n'
                   'set_false_path -to [get_cells {missing_reg*}]\n')
    rules = {(f['rule'], f['endpoint']) for f in run(db, dict(CLOCKS, check=str(bad)))['findings']}
    assert ('sdc.unmatched_clock', 'nothere') in rules
    assert ('sdc.unmatched_endpoint', 'missing_reg*') in rules
    assert ('sdc.unconstrained_clock', 'clkB') in rules
    assert ('sdc.unconstrained_crossing', 's0') in rules


def test_clock_groups_cover(tmp_path):
    db = design(tmp_path)
    f = tmp_path / 'g.sdc'
    f.write_text(SDC_GOOD.splitlines()[0] + '\n' + SDC_GOOD.splitlines()[1] + '\n'
                 'set_clock_groups -asynchronous -group {clkA div} -group [get_clocks clkB]\n')
    r = run(db, dict(CLOCKS, check=str(f)))
    assert 'sdc.unconstrained_crossing' not in {x['rule'] for x in r['findings']}


def test_backend_and_emit(tmp_path):
    from rvw.lint import emit
    db = design(tmp_path)
    p = tmp_path / 'lint.json'
    (tmp_path / 'c.sdc').write_text(SDC_GOOD)
    p.write_text(json.dumps(dict(schema='rvw.lint-settings/1', config='c', top='Top', db=str(db),
                                 backends=['sdc'], sdc=dict(CLOCKS, check='c.sdc'))))
    r = report(p)
    assert r['backends']['sdc']['status'] == 'completed'
    assert r['backends']['sdc']['check']['path'].endswith('c.sdc')
    out = emit.write(r, [], tmp_path / 'emit')
    assert (tmp_path / 'emit/constraints.sdc').read_text().startswith('# Generated by rvw lint')
    assert out['obligations'] == 0
