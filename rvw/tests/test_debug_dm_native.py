"""Debug compliance campaign against native Spike over remote_bitbang (slow; needs Spike and GCC)."""
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from rvw.debug import profile, suite

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / 'fixtures/debug'
TOOLCHAIN = Path(os.environ.get('RISCV_TOOLCHAIN', '/opt/homebrew/opt/riscv-gnu-toolchain'))


@pytest.fixture
def spike_port(tmp_path):
    gcc = shutil.which('riscv64-unknown-elf-gcc') or str(TOOLCHAIN / 'bin/riscv64-unknown-elf-gcc')
    if not shutil.which('spike') or not Path(gcc).is_file():
        pytest.skip('native Spike and RISC-V GCC are needed')
    elf = tmp_path / 'loop.elf'
    subprocess.run([gcc, '-nostdlib', '-march=rv64imac', '-mabi=lp64',
                    '-Wl,-Ttext=0x80000000,--no-relax,-z,max-page-size=4096', '-o', str(elf),
                    str(FIXTURES / 'loop.S')], check=True, timeout=30)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    log = (tmp_path / 'spike.log').open('w')
    process = subprocess.Popen(['spike', f'--rbb-port={port}', '--halted', '-p2', '--dm-sba=64',
                                '-m0x7ffff000:0x1001000', str(elf)], stdout=log, stderr=log,
                               start_new_session=True)
    try:
        deadline = time.monotonic() + 10
        while 'Listening' not in (tmp_path / 'spike.log').read_text():
            assert process.poll() is None and time.monotonic() < deadline, (tmp_path / 'spike.log').read_text()
            time.sleep(0.05)
        yield port
    finally:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(10)
        log.close()


def test_spike_debug_profile(spike_port, tmp_path):
    prof = profile.load(ROOT / 'examples/debug/spike.toml')
    prof['transport']['port'] = spike_port
    entries = suite.run(prof)
    by_status = {}
    for entry in entries:
        by_status.setdefault(entry['status'], []).append(entry['id'])
    assert not by_status.get('fail'), [e for e in entries if e['status'] == 'fail']
    assert len(by_status['pass']) >= 55
    results = suite.to_c3(entries, prof)
    (tmp_path / 'results.json').write_text(json.dumps(results))
    assert suite.verdict(results)[0] in ('pass', 'inconclusive')


def test_spike_tap(spike_port):
    from rvw.debug import dmi, tap
    transport = dmi.SocketJtag('127.0.0.1', spike_port)
    try:
        result = {e['id']: e['status'] for e in tap.run(transport, idcode=0xdeadbeef)}
    finally:
        transport.close()
    assert result.pop('tap.sticky_busy') in ('pass', 'inconclusive')
    assert set(result.values()) == {'pass'}, result


def build_interop(tmp_path):
    gcc = shutil.which('riscv64-unknown-elf-gcc') or str(TOOLCHAIN / 'bin/riscv64-unknown-elf-gcc')
    if not Path(gcc).is_file():
        pytest.skip('native RISC-V GCC is needed')
    elf = tmp_path / 'interop.elf'
    subprocess.run([gcc, '-g', '-nostdlib', '-march=rv64im', '-mabi=lp64',
                    '-Wl,-Ttext=0x80000000,--no-relax,-z,max-page-size=4096', '-o', str(elf),
                    str(FIXTURES / 'interop.S')], check=True, timeout=30)
    return elf


def interop_tools():
    from rvw.debug import interop
    if not shutil.which('openocd'):
        pytest.skip('native OpenOCD is needed')
    try:
        interop.find_gdb()
    except FileNotFoundError:
        pytest.skip('a RISC-V GDB is needed')


def test_interop_reference_model(tmp_path):
    from rvw.debug import interop
    interop_tools()
    elf = build_interop(tmp_path)
    prof = profile.normalize({'scratch': 0x80010000, 'memory': [{'base': 0x7ffff000, 'size': 0x1001000}],
                              'triggers': {'count': 4, 'types': [2, 6]}, 'abstract': ['gpr', 'csr', 'memory'],
                              'datacount': 4, 'sba': {}})
    result = interop.run(profile=prof, elf=elf, out=tmp_path / 'out', timeout=240)
    assert result['status'] == 'pass', (tmp_path / 'out/gdb.log').read_text()
    assert 'reset_halt' in result['checks'] and result['gdb_version'] and result['openocd_version']


def test_interop_spike(tmp_path):
    from rvw.debug import interop
    interop_tools()
    if not shutil.which('spike'):
        pytest.skip('native Spike is needed')
    elf = build_interop(tmp_path)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    log = (tmp_path / 'spike.log').open('w')
    process = subprocess.Popen(['spike', f'--rbb-port={port}', '--halted', '-m0x7ffff000:0x1001000', str(elf)],
                               stdout=log, stderr=log, start_new_session=True)
    try:
        deadline = time.monotonic() + 10
        while 'Listening' not in (tmp_path / 'spike.log').read_text():
            assert process.poll() is None and time.monotonic() < deadline
            time.sleep(0.05)
        result = interop.run(port=port, elf=elf, out=tmp_path / 'out', timeout=240, reset_pc=0x1000,
                             idcode=0xdeadbeef)
    finally:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(10)
        log.close()
    if result['status'] == 'pass':
        return
    # Known finding: OpenOCD 0.12.0+dev skips triggers whose tdata1.type reads 15, and Spike resets
    # every trigger to type 15, so hardware breakpoints and watchpoints cannot be set.
    assert {f.split(':')[0] for f in result['failures']} == {'hardware_breakpoint', 'watchpoint'}, result
    assert 'unknown type 15' in (tmp_path / 'out/openocd.log').read_text() or \
        "Couldn't find an available hardware trigger" in (tmp_path / 'out/openocd.log').read_text()
    assert set(result['checks']) >= {'load', 'register_write', 'memory_write', 'breakpoint', 'stepi', 'reset_halt'}
