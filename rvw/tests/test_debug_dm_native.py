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
