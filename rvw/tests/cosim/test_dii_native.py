"""Opt-in native Sail DII transport. This test does not execute a DUT."""
import os
from pathlib import Path
import socket
import subprocess
import time

import pytest

from rvw.common.proc import kill_group
from rvw.cosim.dii import Token, exchange


def test_sail_dii_reset_and_register_dependency(tmp_path):
    executable = os.environ.get('RVW_TEST_DII_SAIL')
    if not executable:
        pytest.skip('set RVW_TEST_DII_SAIL to a native Sail with --rvfi-dii')
    assert Path(executable).is_file()
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
                # addi x1,x0,5; addi x2,x1,3
                packets = exchange(connection, [Token(0x00500093), Token(0x00308113)], timeout=5)
                assert [p.rd_wdata for p in packets] == [5, 8]
                assert [p.pc_rdata for p in packets] == [0x80000000, 0x80000004]
                # New stream must see x1 reset: addi x2,x1,3.
                packets = exchange(connection, [Token(0x00308113)], timeout=5)
                assert len(packets) == 1 and packets[0].rd_wdata == 3
                assert packets[0].order == 0 and packets[0].pc_rdata == 0x80000000
        finally:
            kill_group(process)
