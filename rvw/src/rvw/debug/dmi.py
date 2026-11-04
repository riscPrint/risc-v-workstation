"""RISC-V Debug 0.13.2 DMI over the remote_bitbang JTAG protocol.

Single TAP, five-bit IR, DTMCS 0x10, DMI 0x11. No physical adapter.
"""
import socket


class RemoteDMI:
    def __init__(self, host, port, *, timeout=5, retries=32):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.retries = retries
        self.reset()
        self.ir(0x10)
        dtmcs = self.scan(0, 32)
        if dtmcs & 15 != 1:
            self.close()
            raise ValueError('DTM version must be 1 (Debug 0.13)')
        self.abits = (dtmcs >> 4) & 63
        if not 1 <= self.abits <= 32:
            self.close()
            raise ValueError('invalid DMI address width')
        self.idle = (dtmcs >> 12) & 7
        self.ir(0x11)

    def close(self):
        self.sock.close()

    def clock(self, tms=0, tdi=0):
        low = (tms << 1) | tdi
        # remote_bitbang samples TDO before the rising edge.
        self.sock.sendall(bytes((48 + low, 82, 52 + low)))
        reply = self.sock.recv(1)
        if reply not in (b'0', b'1'):
            raise ValueError('invalid remote_bitbang TDO')
        return int(reply)

    def reset(self):
        for _ in range(5):
            self.clock(1)
        self.clock(0)

    def ir(self, value):
        for tms in (1, 1, 0, 0):
            self.clock(tms)
        self.shift(value, 5)

    def shift(self, value, bits):
        result = 0
        for bit in range(bits):
            result |= self.clock(int(bit == bits - 1), (value >> bit) & 1) << bit
        self.clock(1)
        self.clock(0)
        return result

    def scan(self, value, bits):
        for tms in (1, 0, 0):
            self.clock(tms)
        return self.shift(value, bits)

    def access(self, address, data=0, *, write=False):
        if not 0 <= address < 1 << self.abits or not 0 <= data < 1 << 32:
            raise ValueError('DMI address/data out of range')
        request = (address << 34) | (data << 2) | (2 if write else 1)
        width = 34 + self.abits
        self.scan(request, width)
        for _ in range(self.retries):
            for _ in range(self.idle + 1):
                self.clock()
            response = self.scan(0, width)
            status = response & 3
            if status == 0:
                return (response >> 2) & 0xffffffff
            if status != 3:
                raise RuntimeError(f'DMI request failed: status {status}')
            # Sticky busy must be cleared before retrying the request.
            self.ir(0x10)
            self.scan(1 << 16, 32)
            self.ir(0x11)
            self.idle += 1
            for _ in range(self.idle):
                self.clock()
            self.scan(request, width)
        raise TimeoutError('DMI remained busy')
