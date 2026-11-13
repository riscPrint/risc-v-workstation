"""AXI4 cycle agents: 32/64/128-bit data, 32-bit addresses and 4-bit IDs.
AXI4-Lite retains its existing 32-bit profile.

Aligned narrow transfers, FIXED/INCR/WRAP bursts, independent channels,
per-ID response order and exclusive reservations. Optional user/QoS omitted.
"""
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, replace
import random
from .apb import ProtocolError, completion


@dataclass(frozen=True)
class Address:
    address: int = 0
    id: int = 0
    length: int = 0  # AXI AxLEN: number of beats minus one
    size: int = 2
    burst: int = 1
    lock: int = 0
    protection: int = 0
    cache: int = 0


@dataclass(frozen=True)
class Write:
    data: int = 0
    strobe: int = 15
    last: bool = True


@dataclass(frozen=True)
class Response:
    id: int = 0
    response: int = 0
    data: int = 0
    last: bool = True


@dataclass(frozen=True)
class Pins:
    reset_n: int = 1
    awvalid: int = 0
    awready: int = 0
    aw: Address = Address()
    wvalid: int = 0
    wready: int = 0
    w: Write = Write()
    bvalid: int = 0
    bready: int = 0
    b: Response = Response()
    arvalid: int = 0
    arready: int = 0
    ar: Address = Address()
    rvalid: int = 0
    rready: int = 0
    r: Response = Response()


def addresses(a):
    width = 1 << a.size
    span = width * (a.length + 1)
    base = a.address // span * span
    for i in range(a.length + 1):
        value = a.address if a.burst == 0 else a.address + i * width
        yield base + (value - base) % span if a.burst == 2 else value


def data_width(data_bytes):
    if data_bytes not in (4,8,16):
        raise ValueError('AXI data_bytes must be 4, 8 or 16')
    return data_bytes*8


def check_address(a, lite=False, data_bytes=4):
    data_width(data_bytes)
    if not (0 <= a.address < 2**32 and 0 <= a.id < 16 and
            0 <= a.length < 256 and 0 <= a.size <= data_bytes.bit_length()-1 and a.burst in (0, 1, 2)
            and a.lock in (0, 1) and 0 <= a.protection < 8 and 0 <= a.cache < 16):
        raise ProtocolError('AXI_ADDRESS_PROFILE')
    if a.address % (1 << a.size):
        raise ProtocolError('AXI_UNALIGNED_PROFILE')
    if a.burst == 0 and a.length >= 16 or a.burst == 2 and a.length not in (1, 3, 7, 15):
        raise ProtocolError('AXI_BURST_LENGTH')
    if any(x // 4096 != a.address // 4096 for x in addresses(a)):
        raise ProtocolError('AXI_4K_BOUNDARY')
    if a.lock and (a.length not in (0, 1, 3, 7, 15) or
                   (1 << a.size) * (a.length + 1) > 128 or
                   a.address % ((1 << a.size) * (a.length + 1))):
        raise ProtocolError('AXI_EXCLUSIVE_ALIGNMENT')
    if lite and (data_bytes != 4 or a.id or a.length or a.lock or a.size != 2 or a.burst != 1 or a.cache):
        raise ProtocolError('AXIL_PROFILE')


class Monitor:
    """Sample all five channels at one edge. Hook receives completed transfers."""
    def __init__(self, hook=lambda event: None, lite=False, data_bytes=4):
        self.data_bytes = data_bytes
        self.data_bits = data_width(data_bytes)
        self.hook, self.lite = hook, lite
        self.previous = Pins(reset_n=0)
        self.aw, self.w = deque(), deque()
        self.writes, self.reads = defaultdict(deque), defaultdict(deque)
        self.coverage = Counter()
        self.completed = 0

    def sample(self, p):
        old, self.previous = self.previous, p
        if not p.reset_n:
            self.aw.clear(); self.w.clear(); self.writes.clear(); self.reads.clear()
            self.coverage['reset'] += 1
            if p.awvalid or p.wvalid or p.bvalid or p.arvalid or p.rvalid:
                raise ProtocolError('AXI_RESET_VALID')
            return
        # Responses can only refer to requests from an earlier edge.
        for ch in ('aw', 'w', 'b', 'ar', 'r'):
            valid, ready = getattr(p, ch+'valid'), getattr(p, ch+'ready')
            if old.reset_n and getattr(old, ch+'valid') and not getattr(old, ch+'ready'):
                if not valid or getattr(p, ch) != getattr(old, ch):
                    raise ProtocolError('AXI_STABLE_' + ch.upper())
            if valid and not ready:
                self.coverage[('stall', ch)] += 1
        if p.bvalid:
            q = self.writes[p.b.id]
            if not q:
                raise ProtocolError('AXI_B_WITHOUT_WRITE')
            a, beats = q[0]
            self._response(p.b, a)
            if p.bready:
                q.popleft(); self.hook(('write', a, beats, p.b))
                self.coverage[('bresp', p.b.response)] += 1
                self.completed += 1
        if p.rvalid:
            q = self.reads[p.r.id]
            if not q:
                raise ProtocolError('AXI_R_WITHOUT_READ')
            a, beats = q[0]
            self._response(p.r, a)
            if p.r.last != (len(beats) == a.length):
                raise ProtocolError('AXI_RLAST')
            if not 0 <= p.r.data < 1 << self.data_bits:
                raise ProtocolError('AXI_DATA_WIDTH')
            if p.rready:
                beats.append(p.r)
                if p.r.last:
                    q.popleft(); self.hook(('read', a, tuple(beats), p.r))
                self.coverage[('rresp', p.r.response)] += 1
                self.completed += int(p.r.last)
        for ch, queue in (('aw', self.aw), ('ar', None)):
            if getattr(p, ch+'valid'):
                a = getattr(p, ch)
                check_address(a, self.lite, self.data_bytes)
                if getattr(p, ch+'ready'):
                    self.coverage[(ch, a.burst, a.length, a.id, a.lock)] += 1
                    if queue is not None:
                        queue.append(a)
                    else:
                        self.reads[a.id].append((a, []))
        if p.wvalid and p.wready:
            if not 0 <= p.w.data < 1 << self.data_bits or not 0 <= p.w.strobe < 1 << self.data_bytes:
                raise ProtocolError('AXI_WRITE_WIDTH')
            self.w.append(p.w)
        while self.aw and len(self.w) >= self.aw[0].length + 1:
            a = self.aw.popleft()
            beats = tuple(self.w.popleft() for _ in range(a.length+1))
            for i, (beat, addr) in enumerate(zip(beats, addresses(a))):
                if beat.last != (i == a.length):
                    raise ProtocolError('AXI_WLAST')
                mask = ((1 << (1 << a.size)) - 1) << (addr % self.data_bytes)
                if beat.strobe & ~mask:
                    raise ProtocolError('AXI_WSTRB_LANE')
            self.writes[a.id].append((a, beats))

    def _response(self, r, a):
        if r.response not in (0, 1, 2, 3) or r.response == 1 and (not a.lock or self.lite):
            raise ProtocolError('AXI_RESPONSE')

    def finish(self, *, idle_reason=None):
        if self.aw or self.w or any(self.writes.values()) or any(self.reads.values()):
            raise ProtocolError('AXI_OUTSTANDING')
        return completion(self.completed, idle_reason)


class Scoreboard:
    """Byte memory scoreboard hook. Exclusive writes use observed B response."""
    def __init__(self, data_bytes=4):
        data_width(data_bytes)
        self.data_bytes = data_bytes
        self.memory = {}
        self.count = 0

    def observe(self, event):
        kind, a, beats, response = event
        self.count += 1
        if kind == 'write':
            if response.response >= 2 or a.lock and response.response != 1:
                return
            for addr, beat in zip(addresses(a), beats):
                base = addr & ~(self.data_bytes-1)
                for lane in range(self.data_bytes):
                    if beat.strobe >> lane & 1:
                        self.memory[base+lane] = beat.data >> (lane*8) & 255
        else:
            for addr, beat in zip(addresses(a), beats):
                if beat.response >= 2:
                    continue
                for byte in range(addr, addr + (1 << a.size)):
                    if (beat.data >> (8*(byte % self.data_bytes)) & 255) != self.memory.get(byte, 0):
                        raise ProtocolError('AXI_READ_DATA')


class Subordinate:
    """Seeded byte RAM. Different IDs can complete out of order.

    A B or R payload remains fixed until accepted. Exclusive reservations use
    exact address/size/length and are invalidated by overlapping writes.
    """
    def __init__(self, seed=1, buggy=False, data_bytes=4, errors=None):
        data_width(data_bytes)
        self.data_bytes = data_bytes
        self.errors = dict(errors or {})
        self.seed = seed
        self.rng, self.buggy = random.Random(seed), buggy
        self.memory, self.reservations = {}, {}
        self.aw, self.w = deque(), deque()
        self.bs, self.rs = defaultdict(deque), defaultdict(deque)
        self.bhold = self.rhold = None

    def step(self, p, commit=True, driven=None):
        if not p.reset_n:
            self.__init__(seed=self.seed, buggy=self.buggy, data_bytes=self.data_bytes, errors=self.errors)
            return Pins(reset_n=0)
        if self.bhold is None:
            ids = [i for i, q in self.bs.items() if q]
            if ids: self.bhold = self.bs[self.rng.choice(ids)].popleft()
        if self.rhold is None:
            ids = [i for i, q in self.rs.items() if q]
            if ids: self.rhold = self.rs[self.rng.choice(ids)].popleft()
        out = replace(p, awready=int(self.rng.randrange(4)!=0), wready=int(self.rng.randrange(4)!=0),
                      arready=int(self.rng.randrange(4)!=0), bvalid=int(self.bhold is not None),
                      b=self.bhold or Response(), rvalid=int(self.rhold is not None), r=self.rhold or Response())
        if driven is not None:
            out = replace(out, awready=driven.awready, wready=driven.wready, arready=driven.arready)
        if not commit: return out
        if out.bvalid and p.bready: self.bhold = None
        if out.rvalid and p.rready: self.rhold = None
        if out.awvalid and out.awready: self.aw.append(p.aw)
        if out.wvalid and out.wready: self.w.append(p.w)
        if out.arvalid and out.arready:
            a = p.ar
            check_address(a, data_bytes=self.data_bytes)
            if a.lock: self.reservations[a.id] = (a.address, a.size, a.length)
            for i, addr in enumerate(addresses(a)):
                data = sum(self.memory.get((addr & ~(self.data_bytes-1))+lane, 0) << (8*lane) for lane in range(self.data_bytes))
                self.rs[a.id].append(Response(a.id, self.errors.get(('read',addr),int(bool(a.lock))), data ^ int(self.buggy), i==a.length))
        while self.aw and len(self.w) >= self.aw[0].length+1:
            a = self.aw.popleft(); check_address(a, data_bytes=self.data_bytes)
            beats = [self.w.popleft() for _ in range(a.length+1)]
            error = self.errors.get(('write',a.address),0)
            success = error < 2 and (not a.lock or self.reservations.get(a.id) == (a.address, a.size, a.length))
            if success:
                touched = set()
                for addr, beat in zip(addresses(a), beats):
                    for lane in range(self.data_bytes):
                        if beat.strobe >> lane & 1:
                            byte = (addr & ~(self.data_bytes-1))+lane
                            self.memory[byte] = beat.data >> (lane*8) & 255
                            touched.add(byte)
                for ident, (addr, size, length) in list(self.reservations.items()):
                    if touched.intersection(range(addr, addr+(1 << size)*(length+1))):
                        del self.reservations[ident]
            self.reservations.pop(a.id, None)
            self.bs[a.id].append(Response(a.id, error or int(bool(a.lock and success))))
        return out


class Manager:
    def __init__(self, tick, timeout=1000, data_bytes=4):
        data_width(data_bytes)
        self.data_bytes = data_bytes
        self.tick, self.timeout = tick, timeout

    def write(self, a, beats):
        check_address(a, data_bytes=self.data_bytes)
        beats = tuple(beats)
        if len(beats) != a.length+1: raise ValueError('write length')
        aw, index = True, 0
        for _ in range(self.timeout):
            p = self.tick(Pins(awvalid=int(aw), aw=a, wvalid=int(index<len(beats)),
                               w=beats[min(index,len(beats)-1)], bready=1))
            if not p.reset_n: return None
            if aw and p.awready: aw=False
            if index<len(beats) and p.wready: index+=1
            if p.bvalid: return p.b
        raise TimeoutError('AXI write policy timeout')

    def read(self, a):
        check_address(a, data_bytes=self.data_bytes)
        ar, beats = True, []
        for _ in range(self.timeout):
            p = self.tick(Pins(arvalid=int(ar), ar=a, rready=1))
            if not p.reset_n: return None
            if ar and p.arready: ar=False
            if p.rvalid:
                beats.append(p.r)
                if p.r.last: return tuple(beats)
        raise TimeoutError('AXI read policy timeout')


def sequences(seed=1, lite=False):
    rng = random.Random(seed)
    for burst in ((1,) if lite else (0, 1, 2)):
        for length in ((0,) if lite else (0, 1, 3, 7, 15)):
            if burst == 2 and length == 0: continue
            a = Address(0x100, 0 if lite else rng.randrange(16), length, burst=burst)
            yield a, tuple(Write(rng.getrandbits(32), rng.randrange(16), i==length) for i in range(length+1))


def inject(p, channel='w', fault='payload'):
    if fault == 'drop_valid': return replace(p, **{channel+'valid': 0})
    value = getattr(p, channel)
    field = 'address' if channel in ('aw', 'ar') else 'data' if channel in ('w', 'r') else 'response'
    return replace(p, **{channel: replace(value, **{field: getattr(value, field)^1})})


class CocotbAgent:
    """Flat PREFIX_awvalid etc. Lite pins omit IDs, bursts, locks and W/RLAST."""
    def __init__(self, dut, prefix, hook=lambda event: None, lite=False, data_bytes=4):
        self.dut, self.prefix, self.lite = dut, prefix, lite
        self.data_bytes = data_bytes
        self.monitor = Monitor(hook, lite, data_bytes)

    def signal(self, name): return getattr(self.dut, self.prefix+'_'+name)

    def fields(self, ch):
        if ch in ('aw', 'ar'):
            return [('address','addr'), ('protection','prot')] + ([] if self.lite else
                [('id','id'), ('length','len'), ('size','size'), ('burst','burst'), ('lock','lock'), ('cache','cache')])
        if ch == 'w': return [('data','data'), ('strobe','strb')] + ([] if self.lite else [('last','last')])
        return ([('data','data')] if ch=='r' else []) + [('response','resp')] + ([] if self.lite else
            [('id','id')] + ([('last','last')] if ch=='r' else []))

    def pins(self):
        values = {'reset_n': int(self.dut.reset_n.value)}
        for ch, cls in (('aw',Address), ('w',Write), ('b',Response), ('ar',Address), ('r',Response)):
            for suffix in ('valid','ready'): values[ch+suffix] = int(self.signal(ch+suffix).value)
            values[ch] = cls(**{field:int(self.signal(ch+pin).value) for field,pin in self.fields(ch)})
        return Pins(**values)

    def drive(self, p, subordinate=False):
        for ch in ('aw','w','b','ar','r'):
            output = (ch in ('b','r')) == subordinate
            suffix = 'valid' if output else 'ready'
            self.signal(ch+suffix).value = getattr(p,ch+suffix)
            if output:
                for field,pin in self.fields(ch): self.signal(ch+pin).value = int(getattr(getattr(p,ch),field))

    async def run_monitor(self):
        from cocotb.triggers import RisingEdge
        while True:
            await RisingEdge(self.dut.clk)
            self.monitor.sample(self.pins())

    async def run_subordinate(self, seed=1):
        from cocotb.triggers import FallingEdge, RisingEdge
        model = Subordinate(seed, data_bytes=self.data_bytes)
        while True:
            await FallingEdge(self.dut.clk)
            pending = model.step(self.pins(), commit=False)
            self.drive(pending, True)
            await RisingEdge(self.dut.clk)
            model.step(self.pins(), driven=pending)

    async def transfer(self, a, beats=None, timeout=1000, response_stall=0):
        from cocotb.triggers import FallingEdge, RisingEdge
        check_address(a, self.lite, self.data_bytes)
        if type(response_stall) is not int or response_stall<0:
            raise ValueError('response_stall must be a nonnegative cycle count')
        write = beats is not None
        beats = tuple(beats or ())
        if write and len(beats) != a.length+1: raise ValueError('write length')
        address, index, result = True, 0, []
        for _ in range(timeout):
            await FallingEdge(self.dut.clk)
            self.drive(Pins(awvalid=int(write and address), aw=a,
                arvalid=int(not write and address), ar=a, wvalid=int(write and index<len(beats)),
                w=beats[min(index,len(beats)-1)] if beats else Write(),
                bready=int(_>=response_stall), rready=int(_>=response_stall)))
            await RisingEdge(self.dut.clk)
            p = self.pins()
            if not p.reset_n: break
            if address and (p.awready if write else p.arready): address=False
            if write and index<len(beats) and p.wready: index+=1
            if write and p.bvalid and p.bready: result=[p.b]; break
            if not write and p.rvalid and p.rready:
                result.append(p.r)
                if p.r.last: break
        else: raise TimeoutError('AXI cocotb policy timeout')
        await FallingEdge(self.dut.clk)
        self.drive(Pins())
        return tuple(result)
