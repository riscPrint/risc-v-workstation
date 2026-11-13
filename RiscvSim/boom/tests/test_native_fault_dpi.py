"""Check native BOOM evidence without starting a build or simulator."""
import json
import os
from pathlib import Path
import pytest


@pytest.fixture
def evidence():
    root = os.environ.get('RVW_BOOM_NATIVE')
    if not root:
        pytest.skip('RVW_BOOM_NATIVE must name native fault and DPI captures')
    return Path(root)


def load(root, relative):
    return json.loads((root / relative).read_text())


def test_two_native_flips_have_readback_and_full_state_detection(evidence):
    result = load(evidence, 'faults/result.json')
    items = result['details']['fault']['faults']
    assert len(items) == 2 and result['details']['fault']['applied']
    for item in items:
        assert item['applied'] and item['writes'] == 1 and item['applied_cycle'] == 200
        assert int(item['before'], 16) ^ int(item['after'], 16) == 1 << item['bit']
    compared = load(evidence, 'faults/cosim.json')
    assert compared['status'] == 'mismatch'
    assert set(compared['mismatch']['differences']) == {'fflags', 'fcsr', 'csr[0x340]'}


def test_dpi_clean_run_is_complete_with_fp_and_csr_comparison(evidence):
    report = load(evidence, 'dpi-clean-report.json')
    assert report['status'] == 'match' and report['trace_complete']
    assert report['state_coverage']['fp'] and report['state_coverage']['csr_snapshot_steps'] > 0
    result = load(evidence, 'dpi-clean-thread/result.json')
    assert result['status'] == 'pass' and not result['details']['fault']['applied']
    rtl = Path(result['details']['rtl_dir']) / 'BoomTop.v'
    text = rtl.read_text()
    assert 'module LockstepDpi' in text and 'rvw_cosim_observe' in text
    rows = [json.loads(line) for line in (evidence/'dpi-clean-thread/rvfi.jsonl').read_text().splitlines()[1:]]
    assert sum(bool(row.get('fd_valid')) for row in rows) == 40


def test_dpi_catches_later_flags_flip(evidence):
    report = load(evidence, 'dpi-injected-report.json')
    assert report['status'] == 'mismatch'
    assert report['mismatch']['cycle'] >= 200
    assert set(report['mismatch']['differences']) == {'fflags', 'fcsr'}
    # The host stops the process after its first mismatch. It can stop the
    # native thread before that thread logs the DPI status-2 exception.
    assert not report['trace_complete']
    assert report['simulator']['returncode'] != 0
    clean = json.loads((evidence/'dpi-clean-thread/rvfi.jsonl').read_text().splitlines()[0])
    injected = json.loads((evidence/'dpi-injected/rvfi.jsonl').read_text().splitlines()[0])
    assert clean['rtl_sha256'] == injected['rtl_sha256']
