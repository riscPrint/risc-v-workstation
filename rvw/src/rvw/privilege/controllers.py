"""Small versioned reference devices. These are model-based, not DUT results."""

AIA = 'AIA-1.0'
FAST = 'riscv-fast-interrupt-v0.20'
ACLINT = 'ACLINT-v1.0-rc4'


class Imsic:
    def __init__(self, identities=63):
        if not 63 <= identities <= 2047 or (identities + 1) % 64:
            raise ValueError('IMSIC identities must be 64*n-1 in 63..2047')
        self.identities = identities
        self.pending = set(); self.enabled = set()
        self.delivery = False; self.threshold = 0

    def inject(self, identity):
        if 1 <= identity <= self.identities:
            self.pending.add(identity)

    def top(self):
        return min((i for i in self.pending & self.enabled
                    if self.threshold == 0 or i < self.threshold), default=0)

    def claim(self):
        identity = self.top()
        self.pending.discard(identity)
        return identity

    @property
    def irq(self):
        return self.delivery and bool(self.top())

    def indirect(self, selector, value=None):
        if selector == 0x70:
            if value is not None: self.delivery = bool(value & 1)
            return int(self.delivery)
        if selector == 0x72:
            if value is not None:
                if not 0 <= value <= self.identities + 1:
                    raise ValueError('unmodeled threshold WARL choice')
                self.threshold = value
            return self.threshold
        for base, bits in [(0x80, self.pending), (0xc0, self.enabled)]:
            if base <= selector < base + 64 and selector % 2 == 0:
                start = (selector - base) * 32
                if value is not None:
                    for i in range(max(1,start), min(start+64,self.identities+1)):
                        (bits.add if value & (1 << (i-start)) else bits.discard)(i)
                return sum(1 << (i-start) for i in bits if start <= i < start+64)
        raise ValueError('unmodeled IMSIC selector')


class Aplic:
    """AIA 1.0 single-domain source arbitration, direct delivery and MSI drain.

    Delegated sources are routed to independently supplied child domain objects.
    No PLIC claim/complete gateway is imposed on APLIC sources.
    """
    def __init__(self, sources=2):
        self.sources = sources; self.mode = {}; self.level = {}
        self.pending = set(); self.enabled = set(); self.priority = {}
        self.targets = {}; self.children = {}; self.delivery = True
        self.threshold = 0

    def configure(self, source, mode):
        if not 1 <= source <= self.sources or mode not in (0,1,4,5,6,7):
            raise ValueError('invalid APLIC source or mode')
        self.mode[source] = mode
        if mode == 0: self.pending.discard(source)

    def set_level(self, source, level):
        if source in self.children:
            self.children[source].set_level(source,level); return
        old = self.level.get(source,False); self.level[source] = bool(level)
        mode = self.mode.get(source,0)
        if (mode == 4 and level and not old) or (mode == 5 and old and not level):
            self.pending.add(source)

    def eligible(self):
        pending = self.pending | {s for s in range(1,self.sources+1)
            if self.mode.get(s) in (6,7) and self.level.get(s,False) == (self.mode[s] == 6)}
        return [s for s in pending & self.enabled if self.mode.get(s,0) != 0
            and (self.threshold == 0 or self.priority.get(s,1) < self.threshold)]

    def top(self):
        return min(self.eligible(), key=lambda s:(self.priority.get(s,1),s), default=0)

    def claim(self):
        source = self.top()
        self.pending.discard(source)
        return source

    @property
    def irq(self):
        return self.delivery and bool(self.top())

    def msi(self):
        """Emit software/edge pending messages using declared (hart, identity).

        Repeated level-to-MSI rectification is outside this small model.
        """
        messages=[]
        for source in sorted(self.pending & self.enabled):
            if self.mode.get(source) in (6,7):
                raise ValueError('level-to-MSI gateway is not modeled')
            if self.mode.get(source,0) and source in self.targets:
                messages.append(self.targets[source]);self.pending.discard(source)
        return messages


class NestedPriority:
    """v0.20 Smnip threshold grouping and trap/return state."""
    def __init__(self, priority_bits=8, group_bits=8):
        if not 1 <= group_bits <= priority_bits <= 8:
            raise ValueError('invalid implemented priority/group bits')
        self.priority_bits=priority_bits;self.group_bits=group_bits
        self.threshold=1 << priority_bits;self.stack=[]

    def eligible(self, priority):
        mask = ~((1 << (self.priority_bits-self.group_bits))-1)
        return (priority & mask) < (self.threshold & mask)

    def trap(self, priority=None):
        self.stack.append(self.threshold)
        if priority is not None:self.threshold=priority

    def ret(self):
        if not self.stack:raise ValueError('return without a saved threshold')
        self.threshold=self.stack.pop()


class Aclint:
    """ACLINT rc4 MSWI/MTIMER/SSWI semantics; addresses are project data."""
    def __init__(self, harts=1):
        if harts < 1:raise ValueError('ACLINT needs at least one hart')
        self.time=0;self.compare=[(1<<64)-1]*harts
        self.msip=[False]*harts;self.ssip=[False]*harts

    def tick(self, ticks=1):
        if ticks < 0:raise ValueError('ticks must be nonnegative')
        self.time=(self.time+ticks)&((1<<64)-1)

    def write_msip(self, hart, value):self.msip[hart]=bool(value&1)
    def set_ssip(self, hart, value):
        if value&1:self.ssip[hart]=True
    def clear_ssip_csr(self, hart):self.ssip[hart]=False
    def mtip(self, hart):return self.time >= self.compare[hart]
