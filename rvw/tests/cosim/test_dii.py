"""v1 wire fixtures and socket tests. Fake hooks are not native core evidence."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import socket
import struct

import pytest

from rvw.cosim.dii import (Token, Retirement, exchange, compare, receive,
                            deadline, serve_connection)


def test_wire_offsets():
    assert Token(0x12345678, 0x1234).encode() == bytes.fromhex('7856341234120100')
    packet = Retirement(order=1, pc_rdata=2, insn=0x13, rd_addr=3, trap=1, intr=1)
    wire = packet.encode()
    assert len(wire) == 88
    assert wire[:8] == struct.pack('<Q', 1)
    assert wire[24:32] == struct.pack('<Q', 0x13)
    assert wire[84:] == bytes([3, 1, 0, 1])
    assert Retirement.decode(wire) == packet


class Hook:
    def __init__(self):
        self.resets = 0
        self.streams = []
    def reset(self):
        self.resets += 1
    def execute(self, tokens, timeout):
        self.streams.append(tokens)
        return [Retirement(order=i, insn=t.insn) for i, t in enumerate(tokens)]


def test_server_negotiation_timing_and_reset():
    hook = Hook()
    server, client = socket.socketpair()
    with server, client, ThreadPoolExecutor() as pool:
        future = pool.submit(serve_connection, server, hook, max_streams=3, timeout=1)
        client.sendall(Token(0x56455253, cmd=0).encode())
        assert Retirement.decode(receive(client, 88, deadline(1))).halt == 1
        for tick in [2, 65535]:
            assert exchange(client, [Token(0x0001, tick)], timeout=1)[0].insn == 1
        future.result()
    assert hook.resets == 5
    assert [s[0].time for s in hook.streams] == [2, 65535]


@pytest.mark.parametrize('data', [b'\0', b'\0'*7, b''])
def test_truncated_input_resets(data):
    hook = Hook()
    server, client = socket.socketpair()
    with server, client:
        client.sendall(data)
        client.shutdown(socket.SHUT_WR)
        with pytest.raises(EOFError):
            serve_connection(server, hook, timeout=1)
    assert hook.resets == 2


@pytest.mark.parametrize('raw', [b'\0'*7+b'\1', b'\0'*6+b'\2\0'])
def test_invalid_token(raw):
    with pytest.raises(ValueError):
        Token.decode(raw)


def test_deadline():
    a, b = socket.socketpair()
    with a, b, pytest.raises(TimeoutError):
        receive(a, 88, deadline(.01))


@pytest.mark.parametrize('timeout', [0, -1, float('nan'), float('inf')])
def test_invalid_deadline(timeout):
    with pytest.raises(ValueError):
        deadline(timeout)


@pytest.mark.parametrize('kind', ['match', 'mismatch', 'short', 'empty', 'bad-order', 'wrong-token'])
def test_comparison(kind):
    a, aclient = socket.socketpair()
    b, bclient = socket.socketpair()
    def answer(sock, altered):
        receive(sock, 24, deadline(1))
        packets = [Retirement(order=i, insn=0x13) for i in range(2)]
        if altered:
            if kind == 'wrong-token': packets[1] = replace(packets[1], insn=0x93)
            if kind == 'mismatch': packets[1] = replace(packets[1], trap=1)
            if kind == 'short': packets.pop()
            if kind == 'empty': packets.clear()
            if kind == 'bad-order': packets[1] = replace(packets[1], order=0)
        sock.sendall(b''.join(p.encode() for p in packets) + Retirement(halt=1).encode())
    with a, aclient, b, bclient, ThreadPoolExecutor() as pool:
        fa=pool.submit(answer, a, True)
        fb=pool.submit(answer, b, False)
        if kind == 'bad-order':
            with pytest.raises(ValueError): compare(aclient, bclient, [Token(0x13)]*2, timeout=1)
            bclient.sendall(Token(0x13).encode()*2 + Token(cmd=0).encode())
        else:
            result=compare(aclient,bclient,[Token(0x13)]*2,timeout=1)
            expected='inconclusive' if kind in ['short','empty','wrong-token'] else kind
            assert result['status'] == expected
        fa.result(); fb.result()


def test_cli_invalid_file(rvw, tmp_path):
    path=tmp_path/'tokens'
    path.write_bytes(Token(0x13).encode())
    code, _, data=rvw('cosim','dii','replay','--tokens',path,
                       '--core-endpoint','127.0.0.1:1','--sail-endpoint','127.0.0.1:2','--json')
    assert code == 2 and data['status'] == 'error'
