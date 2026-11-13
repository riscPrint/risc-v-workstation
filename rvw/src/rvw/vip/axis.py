"""AXI4-Stream, 32-bit data, keep/strb/last, 2-bit ID/destination, 4-bit user.

TUSER has one bit per byte. Packets can interleave by (TID, TDEST).
Null bytes disappear from packet tokens. Position bytes retain a None value.
"""
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, replace
import random
from .apb import ProtocolError, completion


@dataclass(frozen=True)
class Beat:
    data: int = 0
    keep: int = 15
    strobe: int = 15
    last: bool = True
    id: int = 0
    destination: int = 0
    user: int = 0


@dataclass(frozen=True)
class Pins:
    reset_n: int = 1
    valid: int = 0
    ready: int = 0
    beat: Beat = Beat()


@dataclass(frozen=True)
class Packet:
    id: int
    destination: int
    tokens: tuple  # (data byte or None for a position byte, user bit)


class Monitor:
    """Protocol checks, per-stream packet assembly, coverage and hooks."""
    def __init__(self, packet_hook=lambda p: None, beat_hook=lambda b: None):
        self.packet_hook, self.beat_hook = packet_hook, beat_hook
        self.previous = Pins(reset_n=0)
        self.partial = defaultdict(list)
        self.coverage = Counter()

    def sample(self, p):
        old, self.previous = self.previous, p
        if not p.reset_n:
            self.partial.clear()
            self.coverage['reset'] += 1
            if p.valid:
                raise ProtocolError('AXIS_RESET_VALID')
            return
        if old.reset_n and old.valid and not old.ready:
            if not p.valid or p.beat != old.beat:
                raise ProtocolError('AXIS_STABLE')
        if p.valid:
            b = p.beat
            if b.strobe & ~b.keep:
                raise ProtocolError('AXIS_BYTE_QUALIFIER')
            if not (0 <= b.keep <= 15 and 0 <= b.strobe <= 15 and
                    0 <= b.id <= 3 and 0 <= b.destination <= 3 and 0 <= b.user <= 15
                    and 0 <= b.data < 2**32):
                raise ProtocolError('AXIS_PROFILE_WIDTH')
            if not p.ready:
                self.coverage['stall'] += 1
                return
            key = (b.id, b.destination)
            tokens = self.partial[key]
            for lane in range(4):
                if b.keep & (1 << lane):
                    tokens.append(((b.data >> (8*lane)) & 255 if b.strobe & (1 << lane) else None,
                                   (b.user >> lane) & 1))
            self.coverage[('keep', b.keep)] += 1
            self.coverage[('strobe', b.strobe)] += 1
            self.coverage[('stream', *key)] += 1
            self.coverage[('last', b.last)] += 1
            self.beat_hook(b)
            if b.last:
                self.packet_hook(Packet(*key, tuple(tokens)))
                del self.partial[key]
                self.coverage['packets'] += 1

    def finish(self, *, idle_reason=None):
        if self.partial:
            raise ProtocolError('AXIS_UNTERMINATED_PACKET')
        return completion(self.coverage['packets'], idle_reason)


class Scoreboard:
    """Independent input/output packet comparison. Check drain explicitly."""
    def __init__(self):
        self.expected = defaultdict(deque)
        self.count = 0

    def expect(self, packet):
        self.expected[(packet.id, packet.destination)].append(packet.tokens)

    def observe(self, packet):
        queue = self.expected[(packet.id, packet.destination)]
        if not queue or queue.popleft() != packet.tokens:
            raise ProtocolError('AXIS_PACKET_DATA_ORDER')
        self.count += 1

    def finish(self):
        if not self.count or any(self.expected.values()):
            raise ProtocolError('AXIS_MISSING_PACKET')

    def reset(self):
        self.expected.clear()


class Manager:
    def __init__(self, tick, timeout=1000):
        self.tick, self.timeout = tick, timeout

    def send(self, beat):
        for _ in range(self.timeout):
            p = self.tick(Pins(valid=1, beat=beat))
            if not p.reset_n:
                return False
            if p.ready:
                return True
        raise TimeoutError('AXIS source timeout (test policy)')


class Subordinate:
    """Seeded READY schedule. No dependence on VALID is needed."""
    def __init__(self, seed=1):
        self.rng = random.Random(seed)

    def ready(self):
        return self.rng.randrange(4) != 0


class Fifo:
    """One-entry elastic seeded fixture. Bug variant changes active byte data."""
    def __init__(self, buggy=False):
        self.beat, self.valid, self.buggy = Beat(), 0, buggy

    def step(self, source, ready):
        if not source.reset_n:
            self.valid = 0
        data = self.beat
        if self.buggy:
            data = replace(data, data=data.data ^ 0x01010101)
        output = Pins(source.reset_n, self.valid, int(ready), data)
        accepted = replace(source, ready=int(not self.valid or ready))
        if not source.reset_n:
            self.valid = 0
        elif accepted.ready:
            self.valid = source.valid
            if source.valid:
                self.beat = source.beat
        return accepted, output


def sequences(seed=1, packets=32):
    rng = random.Random(seed)
    # All keep masks, sparse/empty packets, position bytes and byte user bits.
    for keep in range(16):
        yield Beat(rng.getrandbits(32), keep, keep, True, keep % 4, keep // 4, keep)
        yield Beat(rng.getrandbits(32), keep, 0, True, keep % 4, keep // 4, keep)
    # Interleaved streams. TLAST closes each independently.
    yield Beat(1, last=False, id=0)
    yield Beat(2, last=False, id=1)
    yield Beat(3, id=0)
    yield Beat(4, id=1)
    for _ in range(packets):
        ident, dest = rng.randrange(4), rng.randrange(4)
        length = rng.randrange(1, 9)
        for i in range(length):
            keep = rng.randrange(16)
            yield Beat(rng.getrandbits(32), keep, rng.randrange(16) & keep,
                       i+1 == length, ident, dest, rng.randrange(16))


def inject(p, fault='data'):
    if fault == 'data':
        return replace(p, beat=replace(p.beat, data=p.beat.data ^ 1))
    if fault == 'drop_valid':
        return replace(p, valid=0)
    if fault == 'byte_qualifier':
        return replace(p, beat=replace(p.beat, keep=0, strobe=1))
    raise ValueError(f'unknown AXIS fault: {fault}')


class CocotbAgent:
    """Prefix pins: PREFIX_tvalid/tready/tdata/tkeep/tstrb/tlast/tid/tdest/tuser."""
    def __init__(self, dut, prefix, packet_hook=lambda p: None, beat_hook=lambda b: None, timeout=1000):
        self.dut, self.prefix = dut, prefix
        self.monitor = Monitor(packet_hook, beat_hook)
        self.timeout = timeout

    def signal(self, name):
        return getattr(self.dut, self.prefix + '_' + name)

    def pins(self):
        values = [int(self.signal(k).value) for k in ('tdata', 'tkeep', 'tstrb', 'tlast', 'tid', 'tdest', 'tuser')]
        return Pins(int(self.dut.reset_n.value), int(self.signal('tvalid').value),
                    int(self.signal('tready').value), Beat(*values))

    async def run_monitor(self):
        from cocotb.triggers import RisingEdge
        while True:
            await RisingEdge(self.dut.clk)
            self.monitor.sample(self.pins())

    async def send(self, beat):
        from cocotb.triggers import FallingEdge, RisingEdge
        await FallingEdge(self.dut.clk)
        for name, value in zip(('tdata', 'tkeep', 'tstrb', 'tlast', 'tid', 'tdest', 'tuser'), vars(beat).values()):
            self.signal(name).value = int(value)
        self.signal('tvalid').value = 1
        for _ in range(self.timeout):
            await RisingEdge(self.dut.clk)
            p = self.pins()
            if not p.reset_n or p.ready:
                await FallingEdge(self.dut.clk)
                self.signal('tvalid').value = 0
                return bool(p.reset_n)
        raise TimeoutError('AXIS source timeout (test policy)')

    async def run_subordinate(self, seed=1):
        from cocotb.triggers import FallingEdge
        model = Subordinate(seed)
        while True:
            await FallingEdge(self.dut.clk)
            self.signal('tready').value = int(model.ready())
