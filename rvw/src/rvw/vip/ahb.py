"""AHB-Lite, 32-bit little-endian, one manager, single-layer bus.

HREADY is the selected subordinate's HREADYOUT. Pins are pre-update samples
at rising edges. No arbitration, SPLIT, RETRY or AHB5 extensions.
"""
from dataclasses import dataclass, replace
from collections import Counter
import random
from .apb import ProtocolError, completion

LENGTHS = {0: 1, 1: None, 2: 4, 3: 4, 4: 8, 5: 8, 6: 16, 7: 16}


@dataclass(frozen=True)
class Pins:
    reset_n: int = 1
    hsel: int = 1
    htrans: int = 0
    haddr: int = 0
    hwrite: int = 0
    hsize: int = 2
    hburst: int = 0
    hprot: int = 3
    hmastlock: int = 0
    hwdata: int = 0
    hrdata: int = 0
    hready: int = 1
    hresp: int = 0


@dataclass(frozen=True)
class Transfer:
    address: int
    write: bool = False
    data: int = 0
    size: int = 2
    burst: int = 0
    protection: int = 3
    response: int = 0
    error: bool = False
    waits: int = 0
    aborted: bool = False


def next_address(address, size, burst):
    step = 1 << size
    if burst in (2, 4, 6):
        boundary = step * LENGTHS[burst]
        return (address & ~(boundary - 1)) | ((address + step) & (boundary - 1))
    return address + step


class Monitor:
    """Independent address/data pipeline, assertions, functional bins, hook."""
    def __init__(self, hook=lambda t: None):
        self.hook, self.coverage = hook, Counter()
        self.previous = Pins(reset_n=0)
        self.pending = None
        self.waits = 0
        self.last = None
        self.beats = 0

    def sample(self, p):
        old, self.previous = self.previous, p
        if not p.reset_n:
            if self.pending:
                self.hook(replace(self.pending, aborted=True, waits=self.waits))
                self.coverage['reset_abort'] += 1
            self.pending, self.last, self.beats, self.waits = None, None, 0, 0
            return
        if old.reset_n and old.hresp and not old.hready:
            if not (p.hresp and p.hready):
                raise ProtocolError('AHB_ERROR_SECOND')
        elif p.hresp:
            if p.hready or self.pending is None:
                raise ProtocolError('AHB_ERROR_FIRST')
        if old.reset_n and not old.hready:
            if old.htrans >= 2 and not old.hresp:
                fields = ('hsel', 'htrans', 'haddr', 'hwrite', 'hsize', 'hburst', 'hprot', 'hmastlock')
                if any(getattr(old, k) != getattr(p, k) for k in fields):
                    raise ProtocolError('AHB_ADDRESS_STABLE')
            if self.pending and self.pending.write and old.hwdata != p.hwdata:
                raise ProtocolError('AHB_DATA_STABLE')
        if self.pending:
            if p.hready:
                t = replace(self.pending, data=p.hwdata, response=p.hrdata,
                            error=bool(p.hresp), waits=self.waits)
                self.hook(t)
                self.coverage[(t.write, t.error, bool(t.waits), t.burst, t.size)] += 1
                self.pending, self.waits = None, 0
            else:
                self.waits += 1
        if not p.hready:
            return
        if p.hresp and p.htrans != 3:
            self.last = None  # Error permits early burst termination.
        if not p.hsel or p.htrans == 0:
            if self.last and LENGTHS[self.last.burst] and self.beats < LENGTHS[self.last.burst]:
                raise ProtocolError('AHB_BURST_SHORT')
            self.last, self.beats = None, 0
            return
        if p.htrans == 1:  # BUSY does not advance the burst.
            return
        if not 0 <= p.hsize <= 2 or p.haddr % (1 << p.hsize):
            raise ProtocolError('AHB_ALIGNMENT_SIZE')
        t = Transfer(p.haddr, bool(p.hwrite), size=p.hsize, burst=p.hburst, protection=p.hprot)
        if p.htrans == 3:
            last = self.last
            if last is None or last.burst == 0:
                raise ProtocolError('AHB_SEQ')
            if (t.write, t.size, t.burst, t.protection) != (last.write, last.size, last.burst, last.protection):
                raise ProtocolError('AHB_BURST_CONTROL')
            if t.address != next_address(last.address, last.size, last.burst):
                raise ProtocolError('AHB_BURST_ADDRESS')
            if t.address >> 10 != last.address >> 10:
                raise ProtocolError('AHB_1KB')
            self.beats += 1
            if LENGTHS[t.burst] and self.beats > LENGTHS[t.burst]:
                raise ProtocolError('AHB_BURST_LONG')
        else:
            if self.last and LENGTHS[self.last.burst] and self.beats < LENGTHS[self.last.burst]:
                raise ProtocolError('AHB_BURST_SHORT')
            self.beats = 1
        self.pending = self.last = t

    def finish(self, *, idle_reason=None):
        if self.pending is not None:
            raise ProtocolError('AHB_UNFINISHED')
        return completion(sum(v for k,v in self.coverage.items() if isinstance(k,tuple)), idle_reason)


class RegisterScoreboard:
    """256-byte fixture map. Errors have no effects; reset clears all bytes."""
    def __init__(self):
        self.reset()
        self.count = 0

    def reset(self):
        self.memory = bytearray(256)

    def __call__(self, t):
        if t.aborted:
            return
        if t.error != (t.address >= len(self.memory)):
            raise ProtocolError('AHB_RESPONSE')
        if not t.error:
            lane = t.address % 4
            size = 1 << t.size
            if t.write:
                self.memory[t.address:t.address+size] = ((t.data >> (8*lane)) & ((1 << (8*size))-1)).to_bytes(size, 'little')
            else:
                actual = (t.response >> (8*lane)) & ((1 << (8*size))-1)
                expected = int.from_bytes(self.memory[t.address:t.address+size], 'little')
                if actual != expected:
                    raise ProtocolError('AHB_DATA')
        self.count += 1


class Subordinate:
    """Seeded pipelined RAM. Error responses have exactly two cycles."""
    def __init__(self, seed=1, buggy=False):
        self.memory = bytearray(256)
        self.rng, self.buggy = random.Random(seed), buggy
        self.pending, self.remaining, self.error_first = None, 0, False

    def step(self, p):
        if not p.reset_n:
            self.memory[:] = bytes(256)
            self.pending, self.remaining, self.error_first = None, 0, False
            return replace(p, hready=1, hresp=0, hrdata=0)
        ready, error, data = 1, 0, 0
        t = self.pending
        if t:
            if self.remaining:
                ready = 0
                self.remaining -= 1
            elif t.address >= len(self.memory):
                error = 1
                ready = int(self.error_first)
                self.error_first = True
            else:
                base = t.address & ~3
                data = int.from_bytes(self.memory[base:base+4], 'little') ^ int(self.buggy)
                if t.write:
                    lane, size = t.address % 4, 1 << t.size
                    self.memory[t.address:t.address+size] = ((p.hwdata >> (8*lane)) & ((1 << (8*size))-1)).to_bytes(size, 'little')
        if ready:
            self.pending = (Transfer(p.haddr, bool(p.hwrite), size=p.hsize,
                                     burst=p.hburst, protection=p.hprot)
                            if p.hsel and p.htrans >= 2 else None)
            self.remaining = self.rng.randrange(4) if self.pending else 0
            self.error_first = False
        return replace(p, hready=ready, hresp=error, hrdata=data)


def control(t, trans=2, data=0):
    return Pins(htrans=trans, haddr=t.address, hwrite=int(t.write), hsize=t.size,
                hburst=t.burst, hprot=t.protection, hwdata=data)


class Manager:
    """Drive pipelined bursts. tick returns the sample accepted at an edge."""
    def __init__(self, tick, timeout=1000):
        self.tick, self.timeout = tick, timeout

    def accepted(self, p):
        for _ in range(self.timeout):
            got = self.tick(p)
            if not got.reset_n or got.hready:
                return got
        raise TimeoutError('AHB driver timeout (test policy)')

    def burst(self, items):
        items = list(items)
        if not items:
            raise ValueError('empty AHB burst')
        self.accepted(control(items[0]))
        results = []
        for i, t in enumerate(items):
            p = control(items[i+1], 3, t.data) if i+1 < len(items) else Pins(hwdata=t.data)
            got = self.accepted(p)
            results.append(replace(t, response=got.hrdata, error=bool(got.hresp), aborted=not got.reset_n))
            if not got.reset_n:
                break
        return results


def sequences(seed=1):
    rng = random.Random(seed)
    for size in (0, 1, 2):
        for burst in range(8):
            length = LENGTHS[burst] or 5
            start = (1 << size) * 3 if burst in (2, 4, 6) else 0
            for write in (True, False):
                address, items = start, []
                for _ in range(length):
                    items.append(Transfer(address, write, rng.getrandbits(32), size, burst))
                    address = next_address(address, size, burst)
                yield items
    yield [Transfer(256, True, 1)]
    yield [Transfer(256)]


class CocotbAgent:
    """Optional pin adapter. External clock/reset. See Pins for signal names."""
    def __init__(self, dut, hook=lambda t: None, timeout=1000):
        self.dut, self.monitor, self.timeout = dut, Monitor(hook), timeout

    def pins(self):
        return Pins(**{k: int(getattr(self.dut, k).value) for k in Pins.__dataclass_fields__})

    async def run_monitor(self):
        from cocotb.triggers import RisingEdge
        while True:
            await RisingEdge(self.dut.clk)
            self.monitor.sample(self.pins())

    async def accepted(self, p):
        from cocotb.triggers import FallingEdge, RisingEdge
        await FallingEdge(self.dut.clk)
        for name, value in vars(p).items():
            if name not in ('reset_n', 'hrdata', 'hready', 'hresp'):
                getattr(self.dut, name).value = value
        for _ in range(self.timeout):
            await RisingEdge(self.dut.clk)
            got = self.pins()
            if not got.reset_n or got.hready:
                return got
        raise TimeoutError('AHB driver timeout (test policy)')

    async def burst(self, items):
        items = list(items)
        if not items:
            raise ValueError('empty AHB burst')
        await self.accepted(control(items[0]))
        results = []
        for i, t in enumerate(items):
            p = control(items[i+1], 3, t.data) if i+1 < len(items) else Pins(hwdata=t.data)
            got = await self.accepted(p)
            results.append(replace(t, response=got.hrdata, error=bool(got.hresp), aborted=not got.reset_n))
            if not got.reset_n:
                break
        return results

    async def run_subordinate(self, seed=1, buggy=False):
        from cocotb.triggers import FallingEdge, RisingEdge, Timer
        model = Subordinate(seed, buggy)
        # Compute at falling edge, commit model state for the next rising edge.
        while True:
            await FallingEdge(self.dut.clk)
            await Timer(1, unit='ps')
            p = model.step(self.pins())
            for name in ('hrdata', 'hready', 'hresp'):
                getattr(self.dut, name).value = getattr(p, name)


def random_sequences(seed=1, count=32):
    """Reproducible legal bursts with random starts, sizes, direction and data."""
    rng = random.Random(seed)
    for _ in range(count):
        size, burst = rng.randrange(3), rng.randrange(8)
        address = rng.randrange(16) << size
        write = bool(rng.getrandbits(1))
        protection = rng.randrange(16)
        items = []
        for _ in range(LENGTHS[burst] or rng.randrange(1, 17)):
            items.append(Transfer(address, write, rng.getrandbits(32), size, burst, protection))
            address = next_address(address, size, burst)
        yield items


def inject(p, fault='address'):
    """Apply during a wait for address/data faults, or at response completion."""
    if fault == 'address':
        return replace(p, haddr=p.haddr ^ 4)
    if fault == 'write_data':
        return replace(p, hwdata=p.hwdata ^ 1)
    if fault == 'single_cycle_error':
        return replace(p, hresp=1, hready=1)
    raise ValueError(f'unknown AHB fault: {fault}')
