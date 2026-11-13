"""Sampled replay checks real steps; it cannot accept an empty or skipped window."""
import importlib.util
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import pytest

pytestmark = pytest.mark.fast
PATH = Path(__file__).resolve().parents[2] / 'examples/vexiiriscv/rvw/linux/sample.py'
spec = importlib.util.spec_from_file_location('boot_sample', PATH)
sample = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sample)


def effect(i):
    return dict(pc=0x80000000+4*i, pc_next=0x80000004+4*i, insn=0x00108093,
                mode=3, trap=False, rd=1, rd_wdata=i+1, mem_addr=0, mem_rmask=0,
                mem_wmask=0, mem_rdata=0, mem_wdata=0, mem_fault=False, cause=0, tval=0,
                before=[0, i]+[0]*30)


class Model:
    platform = SimpleNamespace(irq_inputs=[3, 7, 9, 11])

    def __init__(self, effects):
        self.effects = iter(effects)
        self.steps = 0

    def step(self, **kw):
        self.steps += 1
        return next(self.effects)

    def environment_inputs(self, levels):
        self.levels = levels


def rows():
    return [dict(effect(i), order=i-2, cycle=i*10, rs1=1, rs2=0, rs1_rdata=i,
                 rs2_rdata=0, intr=False, absolute_order=str(i)) for i in range(2, 4)]


def inputs():
    return dict(schema='rvw.boot-reference-inputs/1', enabled=True, external=[], counters=[], traps=[])


def test_executes_prefix_and_checks_suffix():
    model = Model(effect(i) for i in range(4))
    result = sample.compare(model, rows(), inputs(), 2, 2)
    assert result['status'] == 'match' and result['compared'] == 2
    assert model.steps == 4 and result['fast_forwarded'] == 2


def test_corrupt_suffix_is_a_mismatch():
    records = rows()
    records[1]['rd_wdata'] ^= 1
    result = sample.compare(Model(effect(i) for i in range(4)), records, inputs(), 2, 2)
    assert result['status'] == 'mismatch' and result['compared'] == 1
    assert 'rd_wdata' in result['differences']


def test_empty_missing_or_out_of_order_window_is_refused():
    for records in ([], rows()[:1], rows()[::-1]):
        with pytest.raises(ValueError, match='consecutive'):
            sample.compare(Model([]), records, inputs(), 2, 2)


def test_unrecorded_trap_cannot_be_fast_forwarded():
    first = dict(effect(0), trap=True)
    result = sample.compare(Model([first]), rows(), inputs(), 2, 2)
    assert result['status'] == 'mismatch' and result['compared'] == 0


def test_interrupt_needs_pin_evidence():
    journal = inputs()
    journal['external'] = [dict(event='external_interrupt', seq=0, cycle=0,
                                before_order=0, kind='taken', cause='0x8000000000000007')]
    with pytest.raises(ValueError, match='asserted input'):
        sample.compare(Model([]), rows(), journal, 2, 2)


def test_window_from_another_continuation_is_refused():
    header = {'window': {'from_cycle': '300', 'to_cycle': '1500'}}
    before = {'cycle': '300', 'retired': '14'}
    end = {'cycle': '643', 'retired': '20', 'reference_inputs': {
        'traps': [{'cycle': '618', 'cause': '0x8000000000000007', 'tval': '0x0'}], 'external': []}}
    rows = [{'event': 'trap', 'cycle': 619, 'cause': (1 << 63)+7, 'tval': 0},
            {'event': 'end', 'cycle': 643}]
    with pytest.raises(ValueError, match='trap events differ'):
        sample.validate_window(header, rows, before, end)


def test_counter_input_does_not_hide_a_different_instruction():
    journal = inputs()
    journal['counters'] = [dict(order='0', cycle='0', pc='0x80000000', insn='0xc0102373', rd=6, value='0x1')]
    result = sample.compare(Model([effect(0)]), rows(), journal, 2, 2)
    assert result['status'] == 'mismatch' and result['compared'] == 0
    assert result['reason'] == 'counter access differs'
    assert result['reference']['insn'] == '0x108093'


def test_capture_cannot_start_at_a_later_checkpoint():
    journal = inputs()
    journal['enabled'] = False
    with pytest.raises(ValueError, match='no compact reference input history'):
        sample.compare(Model([]), rows(), journal, 2, 2)


@pytest.mark.parametrize('changed', [None, 'library_sha256', 'source_sha256', 'spike_library_sha256'])
def test_reference_profile_is_bound_to_source_binary_and_spike(tmp_path, changed):
    from rvw.common.capture import Capture
    library = tmp_path / 'fixture.so'
    library.write_bytes(b'not a native execution fixture')
    build = dict(schema='rvw.vexii-reference-build/1', physical_bits=32, pmp_regions=8,
                 name='rvw_vexii_linux', library_sha256=hashlib.sha256(library.read_bytes()).hexdigest(),
                 source_sha256=hashlib.sha256(PATH.with_name('reference-profile.cc').read_bytes()).hexdigest(),
                 spike_library_sha256='a'*64)
    if changed:
        build[changed] = 'b'*64
    Path(str(library)+'.json').write_text(json.dumps(build))
    capture = Capture(tmp_path / 'capture')
    shim = {'dependency': {'sha256': 'a'*64}}
    if changed:
        with pytest.raises(ValueError, match='identity differs'):
            sample.capture_reference(capture, library, shim)
    else:
        result = sample.capture_reference(capture, library, shim)
        assert result['name'] == 'rvw_vexii_linux'
        assert Path(result['library']).read_bytes() == library.read_bytes()
