"""Single-select APB4, 32-bit address/data, PPROT and byte strobes.

Call Monitor.sample once per rising edge, before sequential DUT updates.
PENABLE can be high while this peripheral's PSEL is low on a shared bus.
"""
from dataclasses import dataclass, replace
from collections import Counter
import random


class ProtocolError(AssertionError):
    pass


class NoChecks(ProtocolError):
    status = 'no_checks'


def completion(count, idle_reason=None):
    if not count:
        if not isinstance(idle_reason, str) or not idle_reason.strip():
            raise NoChecks('no_checks: zero completed transactions')
        return {'status': 'idle', 'transactions': 0, 'idle_reason': idle_reason}
    return {'status': 'checked', 'transactions': count}



@dataclass(frozen=True)
class Pins:
    reset_n: int = 1
    psel: int = 0
    penable: int = 0
    paddr: int = 0
    pwrite: int = 0
    pwdata: int = 0
    pstrb: int = 0
    pprot: int = 0
    pready: int = 1
    prdata: int = 0
    pslverr: int = 0


@dataclass(frozen=True)
class Transfer:
    address: int
    write: bool = False
    data: int = 0
    strobe: int = 0
    protection: int = 0
    response: int = 0
    error: bool = False
    waits: int = 0
    aborted: bool = False


class Checker:
    """IHI 0024E sections 3.1-3.4. No artificial protocol wait limit."""
    def __init__(self):
        self.previous = Pins(reset_n=0)

    def sample(self, p: Pins):
        old = self.previous
        self.previous = p
        if not p.reset_n:
            return
        if p.psel and not p.pwrite and p.pstrb:
            raise ProtocolError('APB_READ_STROBE')
        if old.reset_n:
            pending = old.psel and (not old.penable or not old.pready)
            if pending:
                if not (p.psel and p.penable):
                    raise ProtocolError('APB_PHASE')
                # Only write data is required to be stable on writes.
                fields = ['paddr', 'pwrite', 'pprot', 'pstrb']
                if old.pwrite:
                    fields.append('pwdata')
                if any(getattr(p, k) != getattr(old, k) for k in fields):
                    raise ProtocolError('APB_STABLE')
            elif p.psel and p.penable:
                raise ProtocolError('APB_SETUP')
        elif p.psel and p.penable:
            raise ProtocolError('APB_SETUP')


class Monitor:
    """Checker, functional bins and transaction callbacks, including reset aborts."""
    def __init__(self, hook=lambda transfer: None):
        self.checker = Checker()
        self.hook = hook
        self.coverage = Counter()
        self.pending = None
        self.waits = 0

    def sample(self, p: Pins):
        self.checker.sample(p)
        if not p.reset_n:
            if self.pending:
                self.hook(replace(self.pending, aborted=True, waits=self.waits))
                self.coverage['reset_abort'] += 1
            self.pending = None
            self.waits = 0
            return
        if p.psel and not p.penable:
            self.pending = Transfer(p.paddr, bool(p.pwrite), p.pwdata, p.pstrb, p.pprot)
            self.waits = 0
        if p.psel and p.penable:
            if not p.pready:
                self.waits += 1
            else:
                t = replace(self.pending, response=p.prdata, error=bool(p.pslverr), waits=self.waits)
                self.coverage[('write' if t.write else 'read', 'error' if t.error else 'ok',
                               'wait' if t.waits else 'zero_wait')] += 1
                if t.write:
                    self.coverage[('strobe', t.strobe)] += 1
                self.coverage[('protection', t.protection)] += 1
                self.hook(t)
                self.pending = None

    def finish(self, *, idle_reason=None):
        if self.pending is not None:
            raise ProtocolError('APB_UNFINISHED')
        count = sum(v for k, v in self.coverage.items()
                    if isinstance(k, tuple) and k[0] in ('read', 'write'))
        return completion(count, idle_reason)


class RegisterScoreboard:
    """Fixture policy: aligned words below 16; errors have no side effects.

    These address and error policies belong to the fixture, not APB.
    Use a custom Monitor hook for a different register map or error policy.
    """
    def __init__(self):
        self.memory = dict.fromkeys(range(0, 16, 4), 0)
        self.count = 0

    def reset(self):
        self.memory = dict.fromkeys(self.memory, 0)

    def __call__(self, t):
        if t.aborted:
            return
        error = t.address not in self.memory
        if t.error != error:
            raise ProtocolError('APB_RESPONSE')
        if not error:
            if t.write:
                mask = sum(255 << (8 * i) for i in range(4) if t.strobe & (1 << i))
                self.memory[t.address] = (self.memory[t.address] & ~mask) | (t.data & mask)
            elif t.response != self.memory[t.address]:
                raise ProtocolError('APB_DATA')
        self.count += 1


def sequences(seed=1, count=32):
    """Directed byte masks, all words, errors, then reproducible random items."""
    rng = random.Random(seed)
    for address in range(0, 16, 4):
        for mask in (15, 0, 1, 2, 4, 8, 5, 10):
            yield Transfer(address, True, rng.getrandbits(32), mask)
            yield Transfer(address)
    yield Transfer(16, True, 1, 15)
    yield Transfer(16)
    for _ in range(count):
        write = bool(rng.getrandbits(1))
        yield Transfer(rng.choice(range(0, 20, 4)), write, rng.getrandbits(32),
                       rng.randrange(16) if write else 0, rng.randrange(8))


def request(t, *, enable=0):
    return Pins(psel=1, penable=enable, paddr=t.address, pwrite=int(t.write),
                pwdata=t.data, pstrb=t.strobe, pprot=t.protection)


def inject(p, fault):
    """Manager-side violations for checker conformance."""
    if fault == 'address':
        return replace(p, paddr=p.paddr ^ 4)
    if fault == 'drop_select':
        return replace(p, psel=0)
    if fault == 'read_strobe':
        return replace(p, pwrite=0, pstrb=1)
    raise ValueError(f'unknown APB fault: {fault}')


class Subordinate:
    """Seeded four-word RAM model with zero to three waits and error responses."""
    def __init__(self, seed=1, buggy=False):
        self.rng = random.Random(seed)
        self.memory = dict.fromkeys(range(0, 16, 4), 0)
        self.remaining = 0
        self.buggy = buggy

    def step(self, p):
        if not p.reset_n:
            self.memory = dict.fromkeys(self.memory, 0)
            self.remaining = 0
            return replace(p, pready=0, pslverr=0, prdata=0)
        if p.psel and not p.penable:
            self.remaining = self.rng.randrange(4)
        error = p.paddr not in self.memory
        out = replace(p, pready=int(self.remaining == 0), pslverr=int(error),
                      prdata=self.memory.get(p.paddr, 0) ^ int(self.buggy and not p.pwrite))
        if p.psel and p.penable:
            if self.remaining:
                self.remaining -= 1
            elif p.pwrite and not error:
                mask = sum(255 << (8 * i) for i in range(4) if p.pstrb & (1 << i))
                self.memory[p.paddr] = (self.memory[p.paddr] & ~mask) | (p.pwdata & mask)
        return out


class Manager:
    """Cycle-level driver. tick must return sampled Pins, including DUT outputs."""
    def __init__(self, tick, timeout=1000):
        self.tick, self.timeout = tick, timeout

    def transfer(self, t):
        self.tick(request(t))
        for _ in range(self.timeout):
            p = self.tick(request(t, enable=1))
            if not p.reset_n:
                return replace(t, aborted=True)
            if p.pready:
                return replace(t, response=p.prdata, error=bool(p.pslverr))
        raise TimeoutError('APB driver timeout (test policy)')


class CocotbAgent:
    """Pin adapter. Start run_monitor once. Use one active role per interface.

    The clock and reset are external. Signals use lower-case Pins field names.
    Output changes occur on falling edges; inputs are sampled at rising edges.
    """
    def __init__(self, dut, hook=lambda transfer: None, timeout=1000):
        self.dut, self.monitor, self.timeout = dut, Monitor(hook), timeout

    def pins(self):
        return Pins(**{name: int(getattr(self.dut, name).value) for name in Pins.__dataclass_fields__})

    async def run_monitor(self):
        from cocotb.triggers import RisingEdge
        while True:
            await RisingEdge(self.dut.clk)
            self.monitor.sample(self.pins())

    async def transfer(self, t):
        from cocotb.triggers import FallingEdge, RisingEdge
        await FallingEdge(self.dut.clk)
        for name, value in vars(request(t)).items():
            if name.startswith('p') and name not in ('pready', 'prdata', 'pslverr'):
                getattr(self.dut, name).value = value
        await RisingEdge(self.dut.clk)
        for _ in range(self.timeout):
            await FallingEdge(self.dut.clk)
            self.dut.penable.value = 1
            await RisingEdge(self.dut.clk)
            p = self.pins()
            if not p.reset_n or p.pready:
                await FallingEdge(self.dut.clk)
                self.dut.psel.value = 0
                self.dut.penable.value = 0
                return replace(t, response=p.prdata, error=bool(p.pslverr), aborted=not p.reset_n)
        raise TimeoutError('APB driver timeout (test policy)')

    async def run_subordinate(self, seed=1, buggy=False):
        from cocotb.triggers import FallingEdge
        model = Subordinate(seed, buggy)
        # step evaluates acceptance for the next rising edge. Requests must be
        # driven before this coroutine reads them (one simulator delta later).
        from cocotb.triggers import Timer
        while True:
            await FallingEdge(self.dut.clk)
            await Timer(1, unit='ps')
            p = model.step(self.pins())
            self.dut.pready.value = p.pready
            self.dut.prdata.value = p.prdata
            self.dut.pslverr.value = p.pslverr
