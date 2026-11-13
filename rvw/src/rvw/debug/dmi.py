"""DMI drivers: JTAG DTM over remote_bitbang or in-process, a direct DMI bus, and a
core adapter's simulated DMI bus over a line protocol (C1 debug transport).

Every driver gives `read(address)` and `write(address, data)` on 32-bit DM registers.
"""
from __future__ import annotations

import os
import re
import select
import socket
import subprocess
import time

from rvw.common.proc import kill_group


class DMIError(RuntimeError):
    pass


class SocketJtag:
    """remote_bitbang client transport: one TCK cycle per call."""

    def __init__(self, host, port, timeout=5):
        self.sock = socket.create_connection((host, port), timeout=timeout)

    def clock(self, tms=0, tdi=0):
        low = (tms << 1) | tdi
        # remote_bitbang samples TDO before the rising edge.
        self.sock.sendall(bytes((48 + low, 82, 52 + low)))
        reply = self.sock.recv(1)
        if reply not in (b'0', b'1'):
            raise ValueError('invalid remote_bitbang TDO')
        return int(reply)

    def clocks(self, sequence):
        """Many TCK cycles in one write; returns TDO for each (tms, tdi) pair."""
        out = bytearray()
        for tms, tdi in sequence:
            low = (tms << 1) | tdi
            out += bytes((48 + low, 82, 52 + low))
        self.sock.sendall(bytes(out))
        reply = bytearray()
        while len(reply) < len(sequence):
            chunk = self.sock.recv(len(sequence) - len(reply))
            if not chunk:
                raise ValueError('remote_bitbang connection closed')
            reply += chunk
        if set(reply) - {48, 49}:
            raise ValueError('invalid remote_bitbang TDO')
        return [b - 48 for b in reply]

    def close(self):
        try:
            self.sock.sendall(b'Q')
        except OSError:
            pass
        self.sock.close()


class JtagDMI:
    """RISC-V JTAG DTM driver. Single TAP. DTMCS 0x10, DMI 0x11."""

    def __init__(self, transport, *, irlen=5, retries=32):
        self.jtag = transport
        self.irlen = irlen
        self.retries = retries
        self.busy_seen = 0
        self.reset()
        self.ir(0x10)
        dtmcs = self.scan(0, 32)
        if dtmcs & 15 != 1:
            self.close()
            raise ValueError('DTM version must be 1 (Debug 0.13/1.0)')
        self.abits = (dtmcs >> 4) & 63
        if not 1 <= self.abits <= 32:
            self.close()
            raise ValueError('invalid DMI address width')
        self.idle = (dtmcs >> 12) & 7
        self.ir(0x11)

    def close(self):
        self.jtag.close()

    def clock(self, tms=0, tdi=0):
        return self.jtag.clock(tms, tdi)

    def _run(self, sequence):
        batch = getattr(self.jtag, 'clocks', None)
        if batch:
            return batch(sequence)
        return [self.jtag.clock(tms, tdi) for tms, tdi in sequence]

    def reset(self):
        self._run([(1, 0)] * 5 + [(0, 0)])

    def _shift_sequence(self, prefix, value, bits):
        body = [(int(bit == bits - 1), (value >> bit) & 1) for bit in range(bits)]
        return [(t, 0) for t in prefix] + body + [(1, 0), (0, 0)]

    def _decode(self, tdo, prefix, bits):
        return sum(bit << i for i, bit in enumerate(tdo[len(prefix):len(prefix) + bits]))

    def ir(self, value):
        prefix = (1, 1, 0, 0)
        return self._decode(self._run(self._shift_sequence(prefix, value, self.irlen)), prefix, self.irlen)

    def scan(self, value, bits):
        prefix = (1, 0, 0)
        return self._decode(self._run(self._shift_sequence(prefix, value, bits)), prefix, bits)

    def idle_cycles(self, count):
        batch = getattr(getattr(self, 'jtag', None), 'clocks', None)
        if batch and count:
            batch([(0, 0)] * count)
        else:
            for _ in range(count):
                self.clock()

    def dtmcs(self, value=0):
        self.ir(0x10)
        result = self.scan(value, 32)
        self.ir(0x11)
        return result

    def dmi_reset(self):
        self.dtmcs(1 << 16)

    def hard_reset(self):
        self.dtmcs(1 << 17)

    def access(self, address, data=0, *, write=False):
        if not 0 <= address < 1 << self.abits or not 0 <= data < 1 << 32:
            raise ValueError('DMI address/data out of range')
        request = (address << 34) | (data << 2) | (2 if write else 1)
        width = 34 + self.abits
        self.scan(request, width)
        for _ in range(self.retries):
            self.idle_cycles(self.idle + 1)
            response = self.scan(0, width)
            status = response & 3
            if status == 0:
                return (response >> 2) & 0xffffffff
            if status != 3:
                raise DMIError(f'DMI request failed: status {status}')
            self.busy_seen = getattr(self, 'busy_seen', 0) + 1
            # Sticky busy must be cleared before retrying the request.
            self.dmi_reset()
            self.idle += 1
            self.idle_cycles(self.idle)
            self.scan(request, width)
        raise TimeoutError('DMI remained busy')

    def read(self, address):
        return self.access(address)

    def write(self, address, data):
        self.access(address, data, write=True)


class RemoteDMI(JtagDMI):
    """JTAG DTM driver over a remote_bitbang TCP server (Spike, a core simulation, rvw debug serve)."""

    def __init__(self, host, port, *, timeout=5, retries=32, irlen=5):
        super().__init__(SocketJtag(host, port, timeout), irlen=irlen, retries=retries)


class BusDMI:
    """Driver over a DMI bus object: `dmi(op, address, data) -> (status, data)`, status 0 ok,
    2 failed, 3 busy. Busy responses are retried after `tick()` when the bus has one."""

    def __init__(self, bus, *, retries=1000):
        self.bus = bus
        self.retries = retries
        self.busy_seen = 0
        self.abits = getattr(bus, 'abits', 7)

    def _op(self, op, address, data):
        for _ in range(self.retries):
            status, value = self.bus.dmi(op, address, data)
            if status == 0:
                return value
            if status != 3:
                raise DMIError(f'DMI request failed: status {status}')
            self.busy_seen += 1
            tick = getattr(self.bus, 'tick', None)
            if tick:
                tick()
        raise TimeoutError('DMI remained busy')

    def read(self, address):
        return self._op(1, address, 0)

    def write(self, address, data):
        self._op(2, address, data & 0xffffffff)

    def close(self):
        close = getattr(self.bus, 'close', None)
        if close:
            close()


class ProcessBus:
    """A core adapter's simulated DMI bus over stdin/stdout (see docs/PLATFORM_CONTRACTS.md, C1).

    rvw writes `r ADDR`, `w ADDR DATA`, `t CYCLES`, `q`. The adapter first prints
    `ready ABITS`, then one `ok DATA`, `busy` or `fail` per `r`/`w`, and `ok 0` per `t`.
    Values are hexadecimal with a `0x` prefix.
    """
    LINE = re.compile(r'^(ok|busy|fail)(?: (0x[0-9a-fA-F]+))?$')

    def __init__(self, command, *, cwd=None, env=None, timeout=10, log=None):
        self.timeout = timeout
        self.log = open(log, 'ab') if log else subprocess.DEVNULL
        self.process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=self.log, start_new_session=True)
        ready = self._line()
        match = re.match(r'^ready (\d+)$', ready)
        if not match:
            self.close()
            raise DMIError(f'adapter did not announce ready: {ready!r}')
        self.abits = int(match.group(1))

    def _line(self):
        stream = self.process.stdout
        deadline = time.monotonic() + self.timeout
        data = b''
        while not data.endswith(b'\n'):
            left = deadline - time.monotonic()
            if left <= 0 or not select.select([stream], [], [], left)[0]:
                raise TimeoutError('DMI adapter did not answer')
            byte = os.read(stream.fileno(), 1)
            if not byte:
                raise DMIError('DMI adapter closed its output')
            data += byte
        return data.decode(errors='replace').strip()

    def _send(self, text):
        self.process.stdin.write(text.encode() + b'\n')
        self.process.stdin.flush()

    def dmi(self, op, address, data):
        self._send(f'r 0x{address:x}' if op == 1 else f'w 0x{address:x} 0x{data:x}')
        reply = self._line()
        match = self.LINE.match(reply)
        if not match:
            raise DMIError(f'invalid adapter reply {reply!r}')
        kind = match.group(1)
        if kind == 'busy':
            return 3, 0
        if kind == 'fail':
            return 2, 0
        return 0, int(match.group(2) or '0x0', 16) & 0xffffffff

    def tick(self, cycles=1):
        self._send(f't {cycles}')
        if not self._line().startswith('ok'):
            raise DMIError('adapter refused a tick')

    def close(self):
        if self.process.poll() is None:
            try:
                self._send('q')
                self.process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired, ValueError):
                pass
        if self.process.poll() is None:
            kill_group(self.process, grace=1)
        if self.log is not subprocess.DEVNULL:
            self.log.close()


def serve_process(dm_bus, stdin, stdout):
    """Run the ProcessBus line protocol over a model bus (used by tests and as an adapter example)."""
    stdout.write(f'ready {getattr(dm_bus, "abits", 7)}\n')
    stdout.flush()
    for line in stdin:
        parts = line.split()
        if not parts:
            continue
        if parts[0] == 'q':
            break
        if parts[0] == 't':
            for _ in range(int(parts[1], 0)):
                dm_bus.dm.tick(1)
            stdout.write('ok 0x0\n')
        elif parts[0] in ('r', 'w'):
            op = 1 if parts[0] == 'r' else 2
            status, value = dm_bus.dmi(op, int(parts[1], 0), int(parts[2], 0) if op == 2 else 0)
            stdout.write({0: f'ok 0x{value:x}\n', 3: 'busy\n'}.get(status, 'fail\n'))
        else:
            stdout.write('fail\n')
        stdout.flush()
