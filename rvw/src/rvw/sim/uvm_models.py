"""Protocol-neutral base environment models shared by Python bench adapters."""
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class Transaction:
    write: bool
    address: int
    data: int


class Scoreboard:
    def __init__(self):
        self.pending = deque()
        self.checks = 0
        self.hit_bins = set()

    def expect(self, transaction):
        self.pending.append(transaction)

    def observe(self, transaction):
        if not self.pending:
            raise AssertionError('unexpected transaction')
        expected = self.pending.popleft()
        if expected != transaction:
            raise AssertionError(f'transaction mismatch: expected {expected}, observed {transaction}')
        self.checks += 1
        self.hit_bins.add((transaction.write, (transaction.address >> 2) & 3))

    def finish(self):
        if self.pending:
            raise AssertionError('expected transactions remain')
        if not self.checks:
            raise AssertionError('no checked transactions')


class Memory:
    """Little-endian bounded memory with byte enables, for CPU memory agents."""
    def __init__(self, base, size):
        if base < 0 or size <= 0:
            raise ValueError('memory needs nonnegative base and positive size')
        self.base, self.data = base, bytearray(size)

    def offset(self, address, size):
        offset = address - self.base
        if size <= 0 or offset < 0 or offset + size > len(self.data):
            raise ValueError('memory access outside declared region')
        return offset

    def read(self, address, size):
        offset = self.offset(address,size)
        return int.from_bytes(self.data[offset:offset+size],'little')

    def write(self, address, value, size, mask=None):
        offset = self.offset(address,size)
        mask = (1 << size)-1 if mask is None else mask
        if value < 0 or value >= 1 << (size*8) or mask < 0 or mask >= 1 << size:
            raise ValueError('data or mask exceeds transfer width')
        for i in range(size):
            if mask & (1 << i):
                self.data[offset+i] = (value >> (8*i)) & 255


class RetirementMonitor:
    """Require contiguous scalar retirement order before reference comparison."""
    def __init__(self, compare):
        self.compare, self.order, self.checked = compare, 0, 0

    def observe(self, record):
        if record.get('order') != self.order:
            raise AssertionError('retirement order gap or duplicate')
        # A comparator must raise on mismatch and return True only after checking.
        if self.compare(record) is not True:
            raise AssertionError('reference comparator produced no checked match')
        self.checked += 1
        self.order += 1

    def finish(self):
        if not self.checked:
            raise AssertionError('no retirement comparisons')


class RegisterModel:
    """RAL mirror using rvw.soc/1 and explicit async bus/backdoor adapters."""
    def __init__(self, path, frontdoor, backdoor=None):
        from rvw.soc.model import load
        self.frontdoor, self.backdoor = frontdoor, backdoor
        self.registers, self.mirror = {}, {}
        for region in load(path)['regions']:
            for register in region['registers']:
                name = region['name'] + '.' + register['name']
                self.registers[name] = {**register, 'address':region['base'] + register['offset']}
                self.mirror[name] = register['reset']

    async def read(self, name, *, check=False):
        reg = self.registers[name]
        if reg['access'] == 'w':
            raise ValueError('frontdoor read of write-only register')
        value = await self.frontdoor.read(reg['address'],reg['width'])
        if value < 0 or value >= 1 << reg['width']:
            raise AssertionError('register read exceeds width')
        expected = self.mirror[name]
        if check and (expected is None or value != expected):
            raise AssertionError('unknown or mismatching register mirror')
        self.mirror[name] = 0 if reg['read_action']=='clear' else value
        return value

    async def write(self, name, value):
        reg = self.registers[name]
        if reg['access'] == 'r' or value < 0 or value >= 1 << reg['width']:
            raise ValueError('illegal frontdoor register write')
        await self.frontdoor.write(reg['address'],value,reg['width'])
        old = self.mirror[name]
        self.mirror[name] = (None if old is None else old & ~value) if reg['write_action']=='one_to_clear' else value

    async def peek(self, name):
        if self.backdoor is None:
            raise ValueError('project backdoor adapter required')
        reg = self.registers[name]
        value = await self.backdoor.read(name,reg['width'])
        if value < 0 or value >= 1 << reg['width']:
            raise AssertionError('backdoor read exceeds width')
        self.mirror[name] = value
        return value

    async def poke(self, name, value):
        if self.backdoor is None:
            raise ValueError('project backdoor adapter required')
        reg = self.registers[name]
        if value < 0 or value >= 1 << reg['width']:
            raise ValueError('backdoor write exceeds width')
        await self.backdoor.write(name,value,reg['width'])
        self.mirror[name] = value
