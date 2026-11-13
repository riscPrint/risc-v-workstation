"""Native Sail DII transport. This test does not execute a DUT."""
import os
from pathlib import Path
import socket
import subprocess
import time

import pytest

from rvw.common.proc import kill_group, run_group
from rvw.cosim.dii import Token, exchange


@pytest.fixture
def sail_connection(tmp_path, request):
    executable = os.environ.get('RVW_TEST_DII_SAIL') or request.getfixturevalue('sail')
    assert Path(executable).is_file()
    capability = run_group([executable, '--help'], timeout=10, capture=True)
    assert capability.returncode == 0, capability.stderr
    if '--rvfi-dii' not in (capability.stdout or '') + (capability.stderr or ''):
        pytest.skip('Installed Sail lacks --rvfi-dii; install the pinned model with '
                    'scripts/install.sh --with-sail --from-bundle --bundle-dir DIR')
    with socket.socket() as allocation:
        allocation.bind(('127.0.0.1', 0))
        port = allocation.getsockname()[1]
    with (tmp_path/'sail.log').open('w') as log:
        process = subprocess.Popen([executable, '--rvfi-dii', str(port)],
                                   stdout=log, stderr=log, start_new_session=True)
        try:
            end = time.monotonic() + 10
            while True:
                try:
                    connection = socket.create_connection(('127.0.0.1', port), .1)
                    break
                except OSError:
                    assert process.poll() is None, (tmp_path/'sail.log').read_text()
                    if time.monotonic() >= end:
                        pytest.fail('Sail did not open its DII port')
                    time.sleep(.1)
            with connection:
                yield connection
        finally:
            kill_group(process)


def test_sail_dii_reset_and_register_dependency(sail_connection):
    connection = sail_connection
    packets = exchange(connection, [Token(0x00500093), Token(0x00308113)], timeout=5)
    assert [p.rd_wdata for p in packets] == [5, 8]
    assert [p.pc_rdata for p in packets] == [0x80000000, 0x80000004]
    packets = exchange(connection, [Token(0x00308113)], timeout=5)
    assert len(packets) == 1 and packets[0].rd_wdata == 3
    assert packets[0].order == 0 and packets[0].pc_rdata == 0x80000000


def test_pygen_runtime_overwrites_nonzero_inputs(sail_connection, tmp_path):
    import shutil
    from rvw.common.proc import run_group
    compiler = os.environ.get('RVW_TEST_DII_GCC') or shutil.which('riscv64-unknown-elf-gcc')
    if not compiler:
        pytest.skip('set RVW_TEST_DII_GCC to a RISC-V GCC')
    runtime = Path(__file__).resolve().parents[3]/'scripts/riscv-dv/user_init.s'
    obj, binary = tmp_path/'runtime.o', tmp_path/'runtime.bin'
    result = run_group([compiler, '-march=rv64i_zicsr', '-mabi=lp64', '-c',
                        '-x', 'assembler', str(runtime), '-o', str(obj)], timeout=30, capture=True)
    assert result.returncode == 0, result.stderr
    result = run_group([compiler.removesuffix('gcc')+'objcopy', '-O', 'binary',
                        '--only-section=.text', str(obj), str(binary)], timeout=30, capture=True)
    assert result.returncode == 0, result.stderr
    raw = binary.read_bytes()
    assert raw and len(raw) % 4 == 0
    setup = [Token((7<<20)|(reg<<7)|0x13) for reg in range(1,32)]
    initialization = [Token(int.from_bytes(raw[i:i+4], 'little')) for i in range(0,len(raw),4)]
    # Probe x31 first, then read each other register through x31. A missing
    # initialization (including x30) leaves the probe value at seven.
    probes = [Token((reg<<15)|(31<<7)|0x13) for reg in [31,*range(1,31)]]
    packets = exchange(sail_connection, setup+initialization+probes, timeout=5)
    assert len(packets) == len(setup+initialization+probes)
    assert [p.rd_wdata for p in packets[-31:]] == [0]*31
