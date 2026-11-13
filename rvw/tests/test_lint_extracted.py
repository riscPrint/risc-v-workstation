"""Run after Test/runMain spinaldb.LintFixtures. No synthetic data in this check."""
import os
from pathlib import Path
import pytest
from rvw.query.db import run_on
from rvw.lint.structural import analyze


@pytest.mark.parametrize('name,expected', [
    ('single', set()), ('unsafe', {'cdc.unsynchronized'}),
    ('sync', {'cdc.sync_candidate'}), ('bus', {'cdc.multi_bit'}),
    ('reset-shared', set()), ('reset-independent', {'rdc.independent_reset', 'rdc.release_order_unproved'}),
    ('reset-async', {'rdc.async_assert_crossing', 'rdc.async_release_unsynchronized', 'rdc.release_order_unproved'}),
])
def test_extracted_reference(name, expected):
    root = os.environ.get('RVW_LINT_FIXTURES')
    if not root:
        pytest.skip('set RVW_LINT_FIXTURES to the extracted reference directory')
    result = run_on(Path(root) / name / 'design.db', analyze)
    assert {f['rule'] for f in result['findings']} == expected
    assert result['status'] == 'inconclusive'


@pytest.mark.parametrize('name,fifo,broken', [
    ('handshake',False,False), ('handshake-broken',False,True),
    ('fifo',True,False), ('fifo-broken',True,True)])
def test_extracted_protocol_topology(name, fifo, broken):
    root = os.environ.get('RVW_LINT_FIXTURES')
    if not root:
        pytest.skip('set RVW_LINT_FIXTURES to the extracted reference directory')
    declaration = dict(kind='async_fifo' if fifo else 'handshake',
                       forward=['a_source','b_first','b_last'],
                       reverse=['b_source','reverse_first','reverse_last'])
    if fifo:
        declaration.update(memory='storage', encoding='gray')
    result = run_on(Path(root) / name / 'design.db', lambda db: analyze(db, {'protocols':[declaration]}))
    assert f"cdc.{declaration['kind']}_" + ('invalid' if broken else 'candidate') in {f['rule'] for f in result['findings']}
    assert result['status'] == 'inconclusive'


@pytest.mark.parametrize('name,merge', [('separate',False), ('reconverge',True)])
def test_extracted_merge(name, merge):
    root = os.environ.get('RVW_LINT_FIXTURES')
    if not root:
        pytest.skip('set RVW_LINT_FIXTURES to the extracted reference directory')
    result = run_on(Path(root) / name / 'design.db', analyze)
    assert ('cdc.reconvergence' in {f['rule'] for f in result['findings']}) == merge


@pytest.mark.parametrize('ordered', [False,True])
def test_extracted_release_order(ordered):
    root = os.environ.get('RVW_LINT_FIXTURES')
    if not root:
        pytest.skip('set RVW_LINT_FIXTURES to the extracted reference directory')
    def check(db):
        domains = list(db.conn.execute('SELECT reset_key FROM clock_domains ORDER BY id'))
        intent = {'reset_order': [[domains[0][0], domains[1][0]]]} if ordered else {}
        return analyze(db, intent)
    result = run_on(Path(root) / 'reset-independent/design.db', check)
    assert ('rdc.release_order_unproved' in {f['rule'] for f in result['findings']}) != ordered


def test_extracted_library_structures():
    """Run after Test/runMain spinaldb.LintLibraryFixtures into the same directory."""
    root = os.environ.get('RVW_LINT_FIXTURES')
    if not root or not (Path(root) / 'library/design.db').exists():
        pytest.skip('set RVW_LINT_FIXTURES with the library fixture')
    from rvw.lint import rules
    result = run_on(Path(root) / 'library/design.db', analyze)
    kinds = {c['destination']: (c['kind'], (c['library'] or {}).get('kind')) for c in result['crossings']}
    assert kinds['a_flagReg_buffercc.buffers_0'] == ('sync_3ff', 'buffer_cc')
    assert kinds['fifo.popToPushGray_buffercc.buffers_0'][0] == 'gray_sync'
    assert kinds['fifo.pushToPopGray_buffercc.buffers_0'][0] == 'gray_sync'
    assert kinds['pulseIn_pulseCCByToggle.inArea_target_buffercc.buffers_0'][0] == 'sync_2ff'
    assert kinds['slow_x'][0] == 'synchronous_related'
    clocks = {c['clock']: c for c in result['cdc']['clocks']}
    assert clocks['a_toggle']['kind'] == 'divided' and clocks['a_toggle']['master'] == 'clkA'
    assert 'cdc.async_fifo_candidate' in {f['rule'] for f in result['findings']}
    bound = [o for o in result['cdc']['obligations'] if o['bind']]
    assert len(bound) == 2 and {o['bind']['module'] for o in bound} == {'StreamFifoCC'}
    release = {d['reset']: d['release'] for d in result['rdc']['domains'] if d['reset']}
    assert release == {'rawReset': 'synchronizer_stages', 'resetB': 'synchronized'}
    lint = run_on(Path(root) / 'library/design.db', lambda d: rules.analyze(d, {}))
    assert lint['status'] == 'completed'


def test_extracted_library_sdc():
    root = os.environ.get('RVW_LINT_FIXTURES')
    if not root or not (Path(root) / 'library/design.db').exists():
        pytest.skip('set RVW_LINT_FIXTURES with the library fixture')
    from rvw.lint import sdc
    r = run_on(Path(root) / 'library/design.db',
               lambda d: sdc.analyze(d, {'clocks': {'clkB': {'period_ns': 8}}}, {}))
    text = r['sdc']
    assert 'create_clock -name clkA -period 10 [get_ports {clkA}]' in text  # Spinal FixedFrequency(100 MHz)
    assert 'create_generated_clock -name a_toggle -source [get_ports {clkA}] -divide_by 2' in text
    assert text.count('set_max_delay -datapath_only') == 3
    assert 'set_false_path -from [get_ports {rawReset}]' in text
    assert r['findings'] == [] and r['spinal_synchronous'] == [['a_toggle', 'clkA']]


def test_extracted_complete_mux():
    root = os.environ.get('RVW_LINT_MUX')
    if not root:
        pytest.skip('set RVW_LINT_MUX to the LintMuxFixture output')
    from rvw.lint.rules import analyze as lint_rules
    result = run_on(Path(root) / 'design.db', lint_rules)
    assert not [f for f in result['findings'] if f['rule'] == 'lint.latch']


def test_extracted_reset_bank():
    root = os.environ.get('RVW_LINT_BANK')
    if not root:
        pytest.skip('set RVW_LINT_BANK to the LintBankFixture output')
    result = run_on(Path(root) / 'design.db', analyze)
    groups = [f for f in result['findings'] if f['rule'] == 'rdc.async_assert_crossing']
    assert len(groups) == 1 and groups[0]['count'] == 4


def test_extracted_toggle_payload():
    root = os.environ.get('RVW_LINT_TOGGLE')
    if not root:
        pytest.skip('set RVW_LINT_TOGGLE to the LintToggleFixture output')
    result = run_on(Path(root) / 'design.db', analyze)
    assert any(c['kind'] == 'qualified_data' for c in result['crossings'])
    assert not any(f['rule'] == 'cdc.comb_before_sync' for f in result['findings'])
    assert result['cdc']['obligations']


def test_extracted_hashed_enum_is_inconclusive():
    root = os.environ.get('RVW_LINT_ENUM')
    if not root:
        pytest.skip('set RVW_LINT_ENUM to the LintEnumFixture output')
    from rvw.lint.rules import analyze as lint_rules
    result = run_on(Path(root) / 'design.db', lint_rules)
    assert result['fsm'][0]['status'] == 'inconclusive'
    assert result['status'] == 'inconclusive'
    assert not any(f['rule'] == 'lint.fsm_unreachable' for f in result['findings'])
