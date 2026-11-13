"""Compile and exercise the real DPI transport without a core model."""
import ctypes
import json
import shutil
import socket
import threading
from pathlib import Path

import pytest
from rvw.common.proc import run_group


@pytest.fixture
def client(tmp_path):
    compiler = shutil.which('c++')
    if not compiler:
        pytest.skip('C++ compiler unavailable')
    source = Path(__file__).resolve().parents[3] / 'Cosim/lockstep_dpi.cc'
    library = tmp_path / 'dpi.so'
    result = run_group([compiler, '-std=c++17', '-shared', '-fPIC', str(source), '-o', str(library)],
                       capture=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    client = ctypes.CDLL(str(library))
    client.rvw_cosim_observe.argtypes = [ctypes.c_char_p]
    client.rvw_cosim_observe.restype = ctypes.c_int
    yield client
    client.rvw_cosim_close()


@pytest.mark.parametrize('reply,expected', [
    ({'status': 'continue'}, 0),
    ({'status': 'match', 'trace_complete': True}, 1),
    ({'status': 'match', 'trace_complete': False}, 2),
    ({'status': 'mismatch'}, 2), ({'status': 'error'}, 2),
    ({'status': 'mismatch', 'harts': {'0': {'status': 'match', 'trace_complete': True}}}, 2),
    ({'status': 'error', 'reproduction': {'status': 'continue'}}, 2),
    ({'status': 'match', 'trace_complete': False, 'harts': {'0': {'trace_complete': True}}}, 2),
    ({'harts': {'0': {'status': 'continue'}}, 'status': 'mismatch'}, 2),
    ({'message': 'escaped \" status \" and }', 'status': 'match', 'trace_complete': True}, 1)])
def test_real_client_reply(client, monkeypatch, reply, expected):
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(1)
    monkeypatch.setenv('RVW_COSIM_PORT', str(listener.getsockname()[1]))
    received = []
    def serve():
        conn, _ = listener.accept()
        with conn, conn.makefile('rwb') as stream:
            received.append(stream.readline())
            stream.write((json.dumps(reply) + '\n').encode())
            stream.flush()
    thread = threading.Thread(target=serve)
    thread.start()
    try:
        assert client.rvw_cosim_observe(b'{"order":0}') == expected
        thread.join(5)
        assert not thread.is_alive()
        assert received == [b'{"order":0}\n']
    finally:
        listener.close()
