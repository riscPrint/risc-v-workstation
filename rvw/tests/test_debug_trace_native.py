"""E-Trace with traps, loss recovery and filters against Spike and the pinned upstream reference (slow)."""
import configparser
import os
import shutil
import subprocess
from pathlib import Path

import pytest

import spike_c2
from rvw.debug import etrace, etrace_flow as ef, api

FIXTURES = Path(__file__).parent / 'fixtures/debug'
TOOLCHAIN = Path(os.environ.get('RISCV_TOOLCHAIN', '/opt/homebrew/opt/riscv-gnu-toolchain'))


@pytest.fixture(scope='module')
def flow(tmp_path_factory):
    reference = os.environ.get('RVW_ETRACE_REFERENCE')
    gcc = TOOLCHAIN / 'bin/riscv64-unknown-elf-gcc'
    if not reference or not shutil.which('spike') or not gcc.is_file():
        pytest.skip('set RVW_ETRACE_REFERENCE; Spike and RISC-V GCC are needed')
    root = etrace.verify_reference(reference)
    tmp = tmp_path_factory.mktemp('etrace')
    elf = tmp / 'traps.elf'
    subprocess.run([str(gcc), '-nostdlib', '-march=rv64imac_zicsr', '-mabi=lp64',
                    '-Wl,-Ttext=0x80000000,--no-relax,-z,max-page-size=4096', '-o', str(elf),
                    str(FIXTURES / 'traps.S')], check=True, timeout=30)
    rvfi = tmp / 'traps.jsonl'
    spike_c2.convert(spike_c2.spike_log(elf, lines=400), rvfi,
                     stop=spike_c2.symbol(elf, 'done', nm=str(TOOLCHAIN / 'bin/riscv64-unknown-elf-nm')))
    config = root / 'referenceFlow/tests/config_files'
    static = tmp / 'static.scf'
    static.write_text((config / 'i_template.scf').read_text())
    user = configparser.ConfigParser()
    user.read(config / 'i_template.ucf')
    user['required']['file-stem'] = str(tmp / 'native')
    user['required']['object-files'] = str(elf)
    ucf = tmp / 'user.ucf'
    with ucf.open('w') as stream:
        user.write(stream)
    return dict(root=root, rvfi=rvfi, scf=static, ucf=ucf, tmp=tmp)


def run_check(flow, **kw):
    return ef.check(flow['root'], flow['rvfi'], flow['scf'], flow['ucf'], toolchain=TOOLCHAIN, **kw)


def test_reference_stream_with_traps_matches_c2(flow):
    rows, complete, _ = ef.retirement(flow['rvfi'])
    assert complete and sum(1 for r in rows if r.get('trap')) >= 4 and {r['mode'] for r in rows} == {0, 3}
    result, expected = run_check(flow)
    assert result['status'] == 'no_checks'
    packets = flow['tmp'] / 'dut.te_inst'
    ef.write_packets(expected, packets)
    result, _ = run_check(flow, packets=packets)
    assert result['status'] == 'flow_match' and result['packets']['status'] == 'packet_match', result


def test_corrupted_encoder_stream_mismatches(flow):
    _, expected = run_check(flow)
    first = next(i for i, p in enumerate(expected) if p['format'] == '1')
    widest = max((i for i, p in enumerate(expected) if p['format'] == '1'), key=lambda i: int(expected[i]['branches']))
    results = {}
    for name, index in (('first', first), ('widest', widest)):
        bad = [dict(p) for p in expected]
        bad[index]['branch_map'] = str(int(bad[index]['branch_map']) ^ 1)
        path = flow['tmp'] / f'bad-{name}.te_inst'
        ef.write_packets(bad, path)
        results[name], _ = run_check(flow, packets=path)
        assert results[name]['packets']['field'] == 'branch_map'
    # The first branch precedes an ecall, so its outcome is never observed: the flow is equal.
    assert results['first']['status'] == 'flow_match'
    assert results['widest']['status'] == 'mismatch'


def test_loss_campaign_recovers_only_at_sync(flow):
    tests = ef.loss_campaign(flow['root'], flow['rvfi'], flow['scf'], flow['ucf'], toolchain=TOOLCHAIN)
    assert tests and {t['status'] for t in tests} == {'pass'}, [t for t in tests if t['status'] != 'pass']
    assert sum(t['unknown_instructions'] for t in tests) > 0
    summary = api.etrace_loss(flow['tmp'] / 'loss', flow['root'], flow['rvfi'], flow['scf'], flow['ucf'], TOOLCHAIN)
    assert summary['status'] == 'pass'


def test_privilege_filter_and_leak(flow):
    machine_only = {'privileges': [3]}
    result, filtered = run_check(flow, filter_spec=machine_only)
    assert 0 < result['qualified'] < result['retired']
    good = flow['tmp'] / 'filtered.te_inst'
    ef.write_packets(filtered, good)
    result, _ = run_check(flow, packets=good, filter_spec=machine_only)
    assert result['status'] == 'flow_match', result
    _, unfiltered = run_check(flow)
    leaky = flow['tmp'] / 'leaky.te_inst'
    ef.write_packets(unfiltered, leaky)
    result, _ = run_check(flow, packets=leaky, filter_spec=machine_only)
    assert result['status'] == 'leak' and result['leaked_pcs']
