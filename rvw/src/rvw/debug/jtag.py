"""IEEE 1149.1 TAP, the RISC-V JTAG DTM, and a remote_bitbang server.

`DTM` wraps any DMI bus object with `dmi(op, address, data) -> (status, data)`:
the Debug Module reference model (`dm.ModelBus`) or a core adapter's simulated
DMI bus (`dmi.ProcessBus`). `BitbangServer` exposes the DTM over OpenOCD's
remote_bitbang protocol, so OpenOCD and GDB can attach to a running simulation.
"""
from __future__ import annotations

import socket
import threading

STATES = ['TLR', 'RTI', 'SELECT_DR', 'CAPTURE_DR', 'SHIFT_DR', 'EXIT1_DR', 'PAUSE_DR', 'EXIT2_DR',
          'UPDATE_DR', 'SELECT_IR', 'CAPTURE_IR', 'SHIFT_IR', 'EXIT1_IR', 'PAUSE_IR', 'EXIT2_IR', 'UPDATE_IR']
# NEXT[state] = (next with TMS=0, next with TMS=1), IEEE 1149.1 figure 6-1.
NEXT = {
    'TLR': ('RTI', 'TLR'), 'RTI': ('RTI', 'SELECT_DR'),
    'SELECT_DR': ('CAPTURE_DR', 'SELECT_IR'), 'CAPTURE_DR': ('SHIFT_DR', 'EXIT1_DR'),
    'SHIFT_DR': ('SHIFT_DR', 'EXIT1_DR'), 'EXIT1_DR': ('PAUSE_DR', 'UPDATE_DR'),
    'PAUSE_DR': ('PAUSE_DR', 'EXIT2_DR'), 'EXIT2_DR': ('SHIFT_DR', 'UPDATE_DR'),
    'UPDATE_DR': ('RTI', 'SELECT_DR'),
    'SELECT_IR': ('CAPTURE_IR', 'TLR'), 'CAPTURE_IR': ('SHIFT_IR', 'EXIT1_IR'),
    'SHIFT_IR': ('SHIFT_IR', 'EXIT1_IR'), 'EXIT1_IR': ('PAUSE_IR', 'UPDATE_IR'),
    'PAUSE_IR': ('PAUSE_IR', 'EXIT2_IR'), 'EXIT2_IR': ('SHIFT_IR', 'UPDATE_IR'),
    'UPDATE_IR': ('RTI', 'SELECT_DR'),
}
IDCODE, DTMCS, DMI, BYPASS = 0x01, 0x10, 0x11, 0x1f


def tms_path(start, end):
    """Shortest TMS sequence from one TAP state to another (breadth-first)."""
    frontier, seen = [(start, [])], {start}
    while frontier:
        state, path = frontier.pop(0)
        if state == end:
            return path
        for tms in (0, 1):
            nxt = NEXT[state][tms]
            if nxt not in seen:
                seen.add(nxt)
                frontier.append((nxt, path + [tms]))
    raise ValueError(f'no TAP path {start} -> {end}')


class DTM:
    """JTAG DTM (Debug 0.13.2/1.0, dtmcs version 1).

    abits: DMI address width. idle: advertised Run-Test/Idle cycles.
    latency: Run-Test/Idle cycles a DMI request stays in progress (busy model).
    """

    def __init__(self, bus, *, abits=7, idle=1, latency=0, irlen=5, idcode=0xdeadbeef):
        self.bus = bus
        self.abits, self.idle, self.latency = abits, idle, latency
        self.irlen = irlen
        self.idcode = idcode | 1
        self.tck = self.tms = self.tdi = 0
        self.tdo = 0
        self.trst_count = 0
        self.history = []          # states entered, for TAP transition checks
        self.hard_reset()

    def hard_reset(self):
        self.state = 'TLR'
        self.ir = IDCODE
        self.ir_shift = 0
        self.dr = 0
        self.dr_len = 1
        self.dmistat = 0
        self.pending = 0           # cycles left for the request in progress
        self.last = (0, 0, 0)      # address, data, status of the last completed request
        self.request = None

    # -- pins ------------------------------------------------------------------
    def set_pins(self, tck, tms, tdi):
        """remote_bitbang semantics: shift on the rising edge, update TDO on the falling edge."""
        if not self.tck and tck:
            if self.state == 'SHIFT_DR':
                self.dr = (self.dr >> 1) | (self.tdi << (self.dr_len - 1))
            elif self.state == 'SHIFT_IR':
                self.ir_shift = (self.ir_shift >> 1) | (self.tdi << (self.irlen - 1))
            self.state = NEXT[self.state][self.tms]
            self.history.append(self.state)
        elif self.tck and not tck:
            self.falling()
        self.tck, self.tms, self.tdi = tck, tms, tdi

    def falling(self):
        state = self.state
        if state == 'TLR':
            self.ir = IDCODE
        elif state == 'RTI':
            self.run_idle()
        elif state == 'CAPTURE_DR':
            self.capture_dr()
        elif state == 'SHIFT_DR':
            self.tdo = self.dr & 1
        elif state == 'UPDATE_DR':
            self.update_dr()
        elif state == 'CAPTURE_IR':
            self.ir_shift = 1      # IEEE 1149.1: the two LSBs capture 01
        elif state == 'SHIFT_IR':
            self.tdo = self.ir_shift & 1
        elif state == 'UPDATE_IR':
            self.ir = self.ir_shift & ((1 << self.irlen) - 1)

    def run_idle(self):
        if self.pending:
            self.pending -= 1
            if not self.pending:
                self._complete()
        tick = getattr(self.bus, 'tick', None)
        if tick:
            tick()

    def _complete(self):
        op, address, data = self.request
        status, value = self.bus.dmi(op, address, data)
        self.last = (address, value if op == 1 else data, 2 if status else 0)
        if status:
            self.dmistat = max(self.dmistat, 2)
        self.request = None

    # -- data registers ----------------------------------------------------------
    def capture_dr(self):
        if self.ir == IDCODE:
            self.dr, self.dr_len = self.idcode, 32
        elif self.ir == DTMCS:
            self.dr = (self.idle << 12) | (self.dmistat << 10) | (self.abits << 4) | 1
            self.dr_len = 32
        elif self.ir == DMI:
            self.dr_len = self.abits + 34
            if self.pending:
                self.dmistat = 3           # sticky busy: scanned while a request was in progress
            address, data, status = self.last
            status = self.dmistat if self.dmistat else status
            self.dr = (address << 34) | (data << 2) | status
        else:
            self.dr, self.dr_len = 0, 1    # BYPASS and unimplemented instructions

    def update_dr(self):
        if self.ir == DTMCS:
            if (self.dr >> 17) & 1:        # dmihardreset
                self.pending = 0
                self.request = None
                self.dmistat = 0
                self.last = (0, 0, 0)
            if (self.dr >> 16) & 1:        # dmireset
                self.dmistat = 0
        elif self.ir == DMI:
            if self.dmistat or self.pending:
                return                     # ignored until dmireset
            op = self.dr & 3
            address = (self.dr >> 34) & ((1 << self.abits) - 1)
            data = (self.dr >> 2) & 0xffffffff
            if op in (1, 2):
                self.request = (op, address, data)
                self.pending = self.latency
                if not self.pending:
                    self._complete()
            elif op == 0:
                pass                       # nop: keeps the previous result for capture

    # -- convenience for in-process drivers --------------------------------------
    def clock(self, tms, tdi=0):
        """One full TCK cycle; returns TDO sampled before the rising edge (remote_bitbang order)."""
        self.set_pins(0, tms, tdi)
        tdo = self.tdo
        self.set_pins(1, tms, tdi)
        return tdo

    def trst(self):
        self.trst_count += 1
        self.state = 'TLR'
        self.ir = IDCODE


class InProcessJtag:
    """Transport object for `dmi.JtagDMI` that clocks a local DTM."""

    def __init__(self, dtm):
        self.dtm = dtm

    def clock(self, tms=0, tdi=0):
        return self.dtm.clock(tms, tdi)

    def close(self):
        pass


class BitbangServer:
    """OpenOCD remote_bitbang server for one DTM. One client at a time; 'Q' ends a client."""

    def __init__(self, dtm, host='127.0.0.1', port=0, *, lock=None):
        self.dtm = dtm
        self.lock = lock or threading.Lock()
        self.listener = socket.create_server((host, port))
        self.port = self.listener.getsockname()[1]
        self.stopped = threading.Event()
        self.thread = None
        self.clients = 0

    def start(self):
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()
        return self

    def serve(self):
        self.listener.settimeout(0.2)
        while not self.stopped.is_set():
            try:
                conn, _ = self.listener.accept()
            except (socket.timeout, OSError):
                continue
            self.clients += 1
            with conn:
                self.handle(conn)

    def handle(self, conn):
        conn.settimeout(0.5)
        while not self.stopped.is_set():
            try:
                chunk = conn.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                return
            if not chunk:
                return
            out = bytearray()
            with self.lock:
                for byte in chunk:
                    char = chr(byte)
                    if '0' <= char <= '7':
                        value = byte - 48
                        self.dtm.set_pins((value >> 2) & 1, (value >> 1) & 1, value & 1)
                    elif char == 'R':
                        out += b'1' if self.dtm.tdo else b'0'
                    elif char in 'rstu':
                        if char in 'su':
                            pass               # srst is a core reset request; not modeled here
                        if char in 'tu':
                            self.dtm.trst()
                    elif char == 'Q':
                        if out:
                            conn.sendall(bytes(out))
                        return
                    # 'B'/'b' (blink) and unknown bytes are ignored
            if out:
                try:
                    conn.sendall(bytes(out))
                except OSError:
                    return

    def stop(self):
        self.stopped.set()
        try:
            self.listener.close()
        except OSError:
            pass
        if self.thread:
            self.thread.join(2)
