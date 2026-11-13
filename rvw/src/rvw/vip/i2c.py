"""Resolved digital I2C. Drive 0 or release; never drive a high level."""
from collections import Counter, deque
from dataclasses import dataclass
import random
from .apb import ProtocolError, completion


def resolve(*pull_low):
    if any(type(v) not in (int, bool) or v not in (0, 1) for v in pull_low):
        raise ProtocolError('I2C_UNKNOWN_DRIVE')
    return int(not any(pull_low))


@dataclass(frozen=True)
class Pins:
    scl: int = 1
    sda: int = 1
    reset_n: int = 1


@dataclass(frozen=True)
class Byte:
    data: int
    ack: bool


class Monitor:
    def __init__(self, hook=lambda byte: None):
        self.hook = hook
        self.coverage = Counter()
        self.reset()

    def reset(self):
        self.previous = Pins()
        self.active = False
        self.bits = self.value = 0

    def sample(self, p):
        if not p.reset_n:
            self.reset()
            self.coverage['reset'] += 1
            return
        if any(v not in (0, 1) for v in (p.scl, p.sda)):
            raise ProtocolError('I2C_UNKNOWN_LINE')
        old, self.previous = self.previous, p
        if old.scl and p.scl and old.sda != p.sda:
            if not p.sda:
                if self.bits > 1: raise ProtocolError('I2C_PARTIAL_BYTE')
                self.bits = self.value = 0
                self.coverage['repeated_start' if self.active else 'start'] += 1
                self.active = True
            else:
                if not self.active or self.bits > 1: raise ProtocolError('I2C_INVALID_STOP')
                self.bits = self.value = 0
                self.active = False
                self.coverage['stop'] += 1
        elif not old.scl and p.scl and self.active:
            if self.bits < 8:
                self.value = (self.value << 1) | p.sda
                self.bits += 1
            else:
                byte = Byte(self.value, not p.sda)
                self.hook(byte)
                self.coverage['ack' if byte.ack else 'nack'] += 1
                self.bits = self.value = 0

    def finish(self, *, idle_reason=None):
        if self.active or self.bits: raise ProtocolError('I2C_UNFINISHED_TRANSFER')
        return completion(self.coverage['ack']+self.coverage['nack'], idle_reason)


class Manager:
    """tick(scl_low, sda_low) returns resolved Pins after settling.

    The callback must resolve all open-drain participants with pull-ups.
    Arbitration loss releases both lines and raises an error.
    """
    def __init__(self, tick, limit=100, resolved_open_drain=True):
        if not resolved_open_drain: raise ValueError('I2C requires resolved open-drain lines')
        if limit < 1: raise ValueError('I2C stretch limit')
        self.tick, self.limit = tick, limit

    def drive(self, scl_low, sda_low):
        p = self.tick(scl_low, sda_low)
        if p.scl not in (0, 1) or p.sda not in (0, 1): raise ProtocolError('I2C_UNKNOWN_LINE')
        if not p.reset_n: raise ProtocolError('I2C_RESET')
        return p

    def high(self, sda_low, arbitrate=False):
        for _ in range(self.limit):
            p = self.drive(0, sda_low)
            if p.scl:
                if arbitrate and not sda_low and not p.sda:
                    self.drive(0, 0)
                    raise ProtocolError('I2C_ARBITRATION_LOST')
                return p
        self.drive(0, 0)
        raise ProtocolError('I2C_STRETCH_TIMEOUT')

    def start(self, repeated=False):
        if repeated: self.drive(1, 0)
        p = self.high(0)
        if not p.sda: raise ProtocolError('I2C_BUS_BUSY')
        self.drive(0, 1)
        self.drive(1, 1)

    def stop(self):
        self.drive(1, 1)
        self.high(1)
        self.drive(0, 0)

    def write(self, data):
        if not 0 <= data <= 255: raise ValueError('I2C byte width')
        for i in range(7, -1, -1):
            low = 1 - ((data >> i) & 1)
            self.drive(1, low)
            self.high(low, arbitrate=True)
            self.drive(1, low)
        self.drive(1, 0)
        ack = not self.high(0).sda
        self.drive(1, 0)
        return ack

    def read(self, ack=False):
        data = 0
        for _ in range(8):
            self.drive(1, 0)
            data = (data << 1) | self.high(0).sda
            self.drive(1, 0)
        self.drive(1, int(ack))
        self.high(int(ack))
        self.drive(1, int(ack))
        self.drive(1, 0)
        return data


class Scoreboard:
    def __init__(self): self.expected = deque(); self.count = 0
    def expect(self, byte): self.expected.append(byte)
    def observe(self, byte):
        if not self.expected or self.expected.popleft() != byte: raise ProtocolError('I2C_BYTE_STREAM')
        self.count += 1
    def finish(self):
        if self.expected or not self.count: raise ProtocolError('I2C_MISSING_BYTE')


def sequences(seed=1, count=32):
    rng = random.Random(seed)
    return [0, 255] + [rng.randrange(256) for _ in range(count)]


class CocotbAgent:
    """Split open-drain enables plus resolved inputs, suitable for two-state RTL.

    PREFIX_scl_low/sda_low are outputs. PREFIX_scl/sda are resolved inputs.
    The RTL must AND released participants and reject active-high drivers.
    """
    def __init__(self, dut, prefix, resolved_open_drain=False, limit=100):
        if not resolved_open_drain: raise ValueError('declare resolved open-drain RTL wiring')
        self.dut, self.prefix, self.limit = dut, prefix, limit
        self.monitor = Monitor()

    def signal(self, name): return getattr(self.dut, self.prefix + '_' + name)

    async def transfer(self, address, data=()):
        from cocotb.triggers import FallingEdge, RisingEdge, ReadOnly
        if not 0 <= address < 128: raise ValueError('I2C 7-bit address')
        # Replay the synchronous controller with a coroutine handshake.
        # Each high phase has an explicit bounded stretch wait.
        async def drive(scl, sda):
            await FallingEdge(self.dut.clk)
            self.signal('scl_low').value = scl
            self.signal('sda_low').value = sda
            await RisingEdge(self.dut.clk)
            await ReadOnly()
            try: p = Pins(int(self.signal('scl').value), int(self.signal('sda').value), int(self.dut.reset_n.value))
            except ValueError as exc: raise ProtocolError('I2C_UNKNOWN_LINE') from exc
            self.monitor.sample(p)
            if not p.reset_n: raise ProtocolError('I2C_RESET')
            return p
        async def high(sda, arbitrate=False):
            for _ in range(self.limit):
                p = await drive(0, sda)
                if p.scl:
                    if arbitrate and not sda and not p.sda:
                        await drive(0, 0)
                        raise ProtocolError('I2C_ARBITRATION_LOST')
                    return p
            await drive(0, 0)
            raise ProtocolError('I2C_STRETCH_TIMEOUT')
        p = await high(0)
        if not p.sda: raise ProtocolError('I2C_BUS_BUSY')
        await drive(0, 1)
        await drive(1, 1)
        acks = []
        for byte in [address << 1, *data]:
            if not 0 <= byte <= 255: raise ValueError('I2C byte width')
            for i in range(7, -1, -1):
                low = 1 - ((byte >> i) & 1)
                await drive(1, low); await high(low, True); await drive(1, low)
            await drive(1, 0)
            acks.append(not (await high(0)).sda)
            await drive(1, 0)
            if not acks[-1]: break
        await drive(1, 1); await high(1); await drive(0, 0)
        self.monitor.finish()
        return acks
