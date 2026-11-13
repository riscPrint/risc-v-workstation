"""A lost remote_bitbang client must not end the disposable RTL session."""
import os
import socket
import struct

import pytest
from rvw.debug.api import tap_run

pytestmark = pytest.mark.native_light('Verilator')


def test_reset_client_then_reconnect(tmp_path):
    port = os.environ.get('RVW_DEBUG_TEST_PORT')
    if not port:
        pytest.skip('set RVW_DEBUG_TEST_PORT to a disposable RTL remote_bitbang endpoint')
    client = socket.create_connection(('127.0.0.1', int(port)), timeout=5)
    # A reset while responses are pending exercises read and flush failures.
    client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
    client.sendall(b'04R' * 64)
    client.close()
    result = tap_run(int(port), tmp_path / 'reconnect')
    assert result['status'] == 'pass', result
