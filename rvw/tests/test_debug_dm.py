"""Debug Module reference model, DMI/JTAG drivers and the compliance campaign (no native tools)."""
import io
import json
import subprocess
import sys
import textwrap
import threading

import pytest

from rvw.debug import dm, dmi, jtag, profile, suite, tap, checks  # noqa: F401
from rvw.debug.hart import Hart, Trap
from rvw.debug.serve import Endpoint
from rvw.results.schema import validate_results

FULL = {
    'harts': 2, 'hart_array': True, 'haltgroups': True, 'scratch': 0x80010000,
    'abstract': ['gpr', 'csr', 'fpr', 'memory', 'quick'], 'datacount': 4, 'progbufsize': 4, 'abstract_latency': 4,
    'hartreset': True, 'unavailable': [], 'triggers': {'count': 4, 'types': [2, 3, 4, 5, 6], 'sizes': [0, 1, 2, 3, 5]},
    'sba': {'latency': 4},
    'memory': [{'base': 0x80000000, 'size': 0x20000}, {'base': 0x10000000, 'size': 0x1000, 'kind': 'error'},
               {'base': 0x11000000, 'size': 0x1000, 'kind': 'readonly'},
               {'base': 0x12000000, 'size': 0x1000, 'kind': 'off'}],
}


def full(**changes):
    raw = {**FULL, **changes}
    return profile.normalize(raw)


def statuses(entries):
    return {e['id']: e['status'] for e in entries}


def test_model_passes_every_declared_check():
    entries = suite.run(full())
    result = statuses(entries)
    assert result.pop('dm.unavailable') == 'unsupported'
    assert set(result.values()) == {'pass'}, [e for e in entries if e['status'] != 'pass']
    assert len(result) >= 75


def test_jtag_level_model_and_reference_comparison():
    prof = full()
    prof['transport'] = {'kind': 'jtag-model'}
    entries = suite.run(prof, groups=['dm', 'abs', 'pb'])
    bad = [e for e in entries if e['status'] not in ('pass', 'unsupported')]
    assert not bad
    assert any('reference_status' in e for e in entries)


def test_minimal_profile_reports_unsupported_not_pass():
    prof = profile.normalize({'progbufsize': 0, 'abstract': ['gpr'], 'scratch': None})
    entries = suite.run(prof)
    result = statuses(entries)
    for name in ('trig.enumerate', 'sba.sizes', 'abs.memory_access', 'abs.quick_access', 'dbg.step'):
        assert result[name] == 'unsupported'
    assert result['abs.gpr_roundtrip'] == 'pass'
    c3 = suite.to_c3(entries, prof)
    assert not validate_results(c3)
    assert all(t['id'] not in ('sba.sizes',) for t in c3['tests'])
    assert {u['id'] for u in c3['unsupported']} >= {'sba.sizes', 'trig.enumerate'}


def mutated(monkeypatch, target, name, replacement):
    monkeypatch.setattr(target, name, replacement)


@pytest.mark.parametrize('mutation,failing', [
    ('ebreak_ignores_dcsr', {'dbg.ebreak_m_exception', 'dbg.ebreak_s', 'dbg.ebreak_u'}),
    ('cmderr_not_sticky', {'abs.cmderr_sticky'}),
    ('progbuf_exception_traps', {'pb.exception'}),
    ('halt_keeps_running', {'dm.halt_stops_execution'}),
    ('triggers_ignore_mode', {'trig.privilege'}),
    ('sba_no_autoincrement', {'sba.autoincrement'}),
    ('no_dmactive_reset', {'dm.dmactive_reset'}),
    ('step_runs_two', {'dbg.step'}),
])
def test_campaign_detects_model_bugs(monkeypatch, mutation, failing):
    from rvw.debug import hart as hartmod, triggers
    if mutation == 'ebreak_ignores_dcsr':
        monkeypatch.setattr(hartmod.Hart, 'ebreak', lambda self: (_ for _ in ()).throw(
            hartmod.DebugEntry(1, self.pc)))
    elif mutation == 'cmderr_not_sticky':
        original = dm.DebugModule.execute
        def execute(self):
            self.cmderr = 0
            return original(self)
        monkeypatch.setattr(dm.DebugModule, 'execute', execute)
    elif mutation == 'progbuf_exception_traps':
        original = hartmod.Hart.run_debug
        def run_debug(self, words, base):
            error = original(self, words, base)
            if error is not None:
                self.csr[hartmod.MCAUSE] = error.cause
            return error
        monkeypatch.setattr(hartmod.Hart, 'run_debug', run_debug)
    elif mutation == 'halt_keeps_running':
        original = dm.DebugModule.tick
        def tick(self, count=None):
            original(self, count)
            for slot in self.slots:
                if slot.hart.debug_mode and not slot.resume_pending:
                    slot.hart.debug_mode = False
                    slot.hart.step()
                    slot.hart.debug_mode = True
        monkeypatch.setattr(dm.DebugModule, 'tick', tick)
    elif mutation == 'triggers_ignore_mode':
        monkeypatch.setattr(triggers.TriggerUnit, '_mode_ok', lambda self, slot, mode: True)
    elif mutation == 'sba_no_autoincrement':
        original = dm.DebugModule._sb_access
        def access(self, *, write):
            saved = self.sb['autoinc']
            self.sb['autoinc'] = 0
            original(self, write=write)
            self.sb['autoinc'] = saved
        monkeypatch.setattr(dm.DebugModule, '_sb_access', access)
    elif mutation == 'no_dmactive_reset':
        original = dm.DebugModule.reset_dm
        def reset_dm(self, power_on=False):
            data = list(getattr(self, 'data', [0] * 12))
            original(self, power_on)
            if not power_on:
                self.data = data
        monkeypatch.setattr(dm.DebugModule, 'reset_dm', reset_dm)
    elif mutation == 'step_runs_two':
        original = hartmod.Hart.step
        def step(self):
            if self.stepping:
                self.stepping = False
                cause = original(self)
                if cause is not None or self.debug_mode:
                    return cause
            return original(self)
        monkeypatch.setattr(hartmod.Hart, 'step', step)
    result = statuses(suite.run(full(), ids=sorted(failing)))
    assert set(result.values()) == {'fail'}, result


def test_reference_comparison_flags_different_observations():
    prof = full()
    prof['transport'] = {'kind': 'dmi_process', 'command': ['unused']}
    target = full(hartsellen=3)
    driver = dmi.BusDMI(dm.ModelBus(dm.DebugModule(target)))
    prof['hartsellen'] = 3
    entries = suite.run(prof, driver=driver, ids=['dm.hartsellen'])
    assert entries[0]['status'] == 'pass' and entries[0]['reference_status'] == 'pass'
    prof2 = full()
    prof2['transport'] = {'kind': 'dmi_process', 'command': ['unused']}
    # A target whose debugver differs from the reference cannot pass on spec rules alone.
    target = dm.DebugModule(full())
    for slot in target.slots:
        slot.hart.debug_version = 3
        slot.hart.dcsr = (3 << 28) | 3
    entries = suite.run(prof2, driver=dmi.BusDMI(dm.ModelBus(target)), ids=['dbg.dcsr_fields'])
    assert entries[0]['status'] == 'fail'


def test_c3_verdicts():
    prof = full()
    assert suite.verdict(suite.to_c3([], prof)) == ('no_checks', 3)
    passing = [{'id': 'a', 'group': 'dm', 'status': 'pass', 'observations': {}, 'dmi_accesses': 1, 'wall_s': 0}]
    assert suite.verdict(suite.to_c3(passing, prof)) == ('pass', 0)
    unclear = passing + [{'id': 'b', 'group': 'dm', 'status': 'inconclusive', 'reason': 'x',
                          'observations': {}, 'dmi_accesses': 1, 'wall_s': 0}]
    results = suite.to_c3(unclear, prof)
    assert not validate_results(results)
    assert suite.verdict(results) == ('inconclusive', 3)
    failing = unclear + [{'id': 'c', 'group': 'dm', 'status': 'fail', 'message': 'm',
                          'observations': {}, 'dmi_accesses': 1, 'wall_s': 0}]
    assert suite.verdict(suite.to_c3(failing, prof)) == ('fail', 1)
    only_unsupported = [{'id': 'd', 'group': 'dm', 'status': 'unsupported', 'reason': 'r'}]
    assert suite.verdict(suite.to_c3(only_unsupported, prof)) == ('no_checks', 3)


def test_profile_skip_is_not_a_pass():
    prof = full(skip={'dm.halt': 'known deviation'})
    entries = suite.run(prof, ids=['dm.halt'])
    assert entries[0]['status'] == 'unsupported' and 'known deviation' in entries[0]['reason']


@pytest.mark.parametrize('raw,message', [
    ({'version': '2.0'}, 'version'), ({'xlen': 16}, 'xlen'), ({'bogus': 1}, 'unknown'),
    ({'modes': 'SU'}, 'modes'), ({'triggers': {'count': 1, 'x': 1}}, 'trigger'),
    ({'transport': {'kind': 'dmi_process'}}, 'command'), ({'skip': {'a': 1}}, 'skip'),
    ({'triggers': {'load_data_timing': 'before'}}, 'load-data'),
])
def test_profile_errors(raw, message):
    with pytest.raises(profile.ProfileError, match=message):
        profile.normalize(raw)


# --- JTAG ----------------------------------------------------------------------------------------
IEEE = {  # IEEE 1149.1 state diagram, independent of jtag.NEXT
    'TLR': ('RTI', 'TLR'), 'RTI': ('RTI', 'SELECT_DR'), 'SELECT_DR': ('CAPTURE_DR', 'SELECT_IR'),
    'CAPTURE_DR': ('SHIFT_DR', 'EXIT1_DR'), 'SHIFT_DR': ('SHIFT_DR', 'EXIT1_DR'),
    'EXIT1_DR': ('PAUSE_DR', 'UPDATE_DR'), 'PAUSE_DR': ('PAUSE_DR', 'EXIT2_DR'),
    'EXIT2_DR': ('SHIFT_DR', 'UPDATE_DR'), 'UPDATE_DR': ('RTI', 'SELECT_DR'),
    'SELECT_IR': ('CAPTURE_IR', 'TLR'), 'CAPTURE_IR': ('SHIFT_IR', 'EXIT1_IR'),
    'SHIFT_IR': ('SHIFT_IR', 'EXIT1_IR'), 'EXIT1_IR': ('PAUSE_IR', 'UPDATE_IR'),
    'PAUSE_IR': ('PAUSE_IR', 'EXIT2_IR'), 'EXIT2_IR': ('SHIFT_IR', 'UPDATE_IR'),
    'UPDATE_IR': ('RTI', 'SELECT_DR'),
}


def model_dtm(**kw):
    module = dm.DebugModule(full())
    module.write(0x10, 1)
    return jtag.DTM(dm.ModelBus(module), **kw), module


def test_tap_transitions_match_ieee():
    dtm, _ = model_dtm()
    for state, (zero, one) in IEEE.items():
        for tms, expected in ((0, zero), (1, one)):
            dtm.state = state
            dtm.clock(tms)
            assert dtm.state == expected, (state, tms)
    assert len(jtag.tms_path('TLR', 'SHIFT_IR')) == 5


@pytest.mark.parametrize('latency', [0, 3])
def test_tap_campaign_on_model(latency):
    dtm, _ = model_dtm(latency=latency)
    result = {e['id']: e['status'] for e in tap.run(jtag.InProcessJtag(dtm), idcode=0xdeadbeef)}
    expected_busy = 'pass' if latency else 'inconclusive'
    assert result.pop('tap.sticky_busy') == expected_busy
    assert set(result.values()) == {'pass'}


def test_tap_campaign_detects_bad_capture(monkeypatch):
    dtm, _ = model_dtm(latency=3)
    original = jtag.DTM.falling
    def falling(self):
        original(self)
        if self.state == 'CAPTURE_IR':
            self.ir_shift = 0
    monkeypatch.setattr(jtag.DTM, 'falling', falling)
    result = {e['id']: e['status'] for e in tap.run(jtag.InProcessJtag(dtm))}
    assert result['tap.ir_capture'] == 'fail'


def test_dmi_driver_busy_retry():
    dtm, module = model_dtm(latency=4, idle=0)
    driver = dmi.JtagDMI(jtag.InProcessJtag(dtm))
    assert driver.abits == 7
    driver.write(0x04, 0x1234)
    assert driver.read(0x04) == 0x1234
    assert driver.busy_seen >= 1 and driver.idle >= 1
    with pytest.raises(ValueError):
        driver.read(1 << 7)


def test_bitbang_server_remote_driver_and_tap():
    endpoint = Endpoint(full(), latency=2, idle=1, ticks_per_ms=10)
    with endpoint:
        driver = dmi.RemoteDMI('127.0.0.1', endpoint.port)
        try:
            driver.write(0x10, 1)
            driver.write(0x10, 0x80000001)
            for _ in range(50):
                if driver.read(0x11) & 0x200:
                    break
            assert driver.read(0x11) & 0x200
        finally:
            driver.close()
        transport = dmi.SocketJtag('127.0.0.1', endpoint.port)
        try:
            result = {e['id']: e['status'] for e in tap.run(transport)}
        finally:
            transport.close()
        assert set(result.values()) == {'pass'}, result


ADAPTER = textwrap.dedent('''
    import sys
    from rvw.debug import dm, dmi, profile
    p = profile.normalize({'scratch': 0x80010000, 'triggers': {'count': 2}})
    dmi.serve_process(dm.ModelBus(dm.DebugModule(p)), sys.stdin, sys.stdout)
''')


def test_process_bus_adapter_transport(tmp_path):
    script = tmp_path / 'adapter.py'
    script.write_text(ADAPTER)
    prof = profile.normalize({'scratch': 0x80010000, 'triggers': {'count': 2},
                              'transport': {'kind': 'dmi_process', 'command': [sys.executable, str(script)]}})
    entries = suite.run(prof, ids=['dm.halt', 'abs.gpr_roundtrip', 'trig.execute_matches', 'dbg.step'])
    assert statuses(entries) == dict.fromkeys(['dm.halt', 'abs.gpr_roundtrip', 'trig.execute_matches',
                                               'dbg.step'], 'pass')
    assert all(e['reference_status'] == 'pass' for e in entries)


def test_process_bus_bad_adapter(tmp_path):
    with pytest.raises(dmi.DMIError):
        dmi.ProcessBus([sys.executable, '-c', 'print("hello")'])
    script = tmp_path / 'busy.py'
    script.write_text('import sys\nprint("ready 7", flush=True)\nfor line in sys.stdin:\n'
                      '    print("busy" if line[0] in "rw" else "ok 0x0", flush=True)\n')
    bus = dmi.BusDMI(dmi.ProcessBus([sys.executable, str(script)]), retries=5)
    try:
        with pytest.raises(TimeoutError):
            bus.read(0x11)
    finally:
        bus.close()


def test_serve_process_protocol():
    stdin = io.StringIO('r 0x11\nw 0x10 0x1\nt 2\nr 0x10\nx\nq\n')
    stdout = io.StringIO()
    dmi.serve_process(dm.ModelBus(dm.DebugModule(full())), stdin, stdout)
    lines = stdout.getvalue().splitlines()
    assert lines[0] == 'ready 7' and lines[2] == 'ok 0x0' and lines[3] == 'ok 0x0'
    assert lines[4] == 'ok 0x1' and lines[5] == 'fail'


def test_cli_suite_writes_c3(tmp_path):
    path = tmp_path / 'p.toml'
    path.write_text('schema = "rvw.debug-profile/1"\nscratch = 0x80010000\n[triggers]\ncount = 2\n')
    out = tmp_path / 'out'
    run = subprocess.run([sys.executable, '-m', 'rvw', 'debug', 'suite', '--profile', str(path), '--out', str(out),
                          '--group', 'dm', '--group', 'trig'], capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stdout + run.stderr
    summary = json.loads(run.stdout)
    assert summary['status'] == 'pass'
    results = json.loads((out / 'results.json').read_text())
    assert not validate_results(results)
    assert results['suite'] == 'debug-compliance' and results['source']['profile_sha256']


def test_hart_model_basics():
    from rvw.debug.hart import Memory, Asm
    memory = Memory([{'base': 0x1000, 'size': 0x100}])
    memory.load(0x1000, Asm.words(Asm.addi(5, 0, -3), Asm.addi(6, 5, 1), Asm.jal(1, 8)))
    hart = Hart(memory, reset_pc=0x1000)
    for _ in range(3):
        assert hart.step() is None
    assert hart.x[5] == (1 << 64) - 3 and hart.x[6] == (1 << 64) - 2 and hart.pc == 0x1010 and hart.x[1] == 0x100c
    with pytest.raises(Trap):
        hart.read_csr(0x7b0)


# --- OpenOCD/GDB interop (no native tools) --------------------------------------------------------
def test_interop_assess_needs_effects():
    from rvw.debug import interop
    every = '\n'.join('RVW_CHECK:' + c for c in interop.CHECKS)
    assert interop.assess('RVW_CONNECTED\n' + every + '\nRVW_COMPLETE', 0, False, expect_reset=False)['status'] == 'pass'
    assert interop.assess('RVW_CONNECTED\nRVW_COMPLETE', 0, False, expect_reset=False)['status'] == 'fail'
    assert interop.assess('RVW_CONNECTED\n' + every, 0, False, expect_reset=False)['status'] == 'inconclusive'
    assert interop.assess('RVW_CONNECTED\n' + every + '\nRVW_COMPLETE', 0, False,
                          expect_reset=True)['status'] == 'fail'
    assert interop.assess(every + '\nRVW_COMPLETE', 0, False, expect_reset=False)['status'] == 'inconclusive'
    assert interop.assess('RVW_CONNECTED\nRVW_FAILURE:breakpoint:pc', 0, False, expect_reset=False)['status'] == 'fail'


def test_interop_c3_attributes_gdb_errors(tmp_path):
    from rvw.debug import interop
    summary = interop.assess('RVW_CONNECTED\nRVW_CHECK:load\nRVW_FAILURE:gdb:Cannot access memory', 0, False,
                             expect_reset=False)
    summary.update(openocd_version='x', target='model')
    interop.write_c3(summary, tmp_path)
    results = json.loads((tmp_path / 'results.json').read_text())
    assert not validate_results(results)
    by_id = {t['id']: t['status'] for t in results['tests']}
    assert by_id['interop.load'] == 'pass' and by_id['interop.register_write'] == 'fail'
    assert by_id['interop.watchpoint'] == 'error'
    assert results['clients']['gdb'] is None


def test_interop_config_and_entry_word(tmp_path):
    from rvw.debug import interop
    text = interop.openocd_config(1234, idcode=0xdeadbeef, log=tmp_path / 'log')
    assert 'remote_bitbang port 1234' in text and 'gdb_port pipe' in text and '-expected-id 0xdeadbeef' in text
    with pytest.raises(ValueError):
        interop.first_word(__file__)
