"""Replay declared accepted PLIC actions independently of DUT instruction results."""
from collections import deque, Counter
import ctypes
from .devices import Plic, PlicMap


class Replay:
    def __init__(self, cpu, declaration):
        if not isinstance(declaration.get('plic'), dict):
            raise ValueError('external interrupt replay requires a declared PLIC model')
        self.cpu = cpu
        self.config = declaration
        self.plic = Plic(PlicMap(**declaration['plic']))
        self.routes = declaration['routes']
        if any(context >= self.plic.map.contexts or pin not in cpu.platform.irq_inputs for context, pin in self.routes):
            raise ValueError('PLIC evidence routes differ from platform inputs')
        initial = declaration.get('initial_levels', [])
        if not isinstance(initial, list) or any(type(source) is not int or not 1 <= source <= self.plic.map.sources for source in initial):
            raise ValueError('invalid initial PLIC source levels')
        for source in initial:
            self.plic.set_level(source, True)
        self.plan = declaration['stimulus']
        self.request = self.ack = None
        if self.plan or 'request_address' in declaration or 'ack_address' in declaration:
            if 'request_address' not in declaration or 'ack_address' not in declaration:
                raise ValueError('PLIC stimuli require request and acknowledgement addresses')
            self.request = int(declaration['request_address'], 16)
            self.ack = int(declaration['ack_address'], 16)
            symbols = cpu.elf.symbols
            if symbols.get('stimulus_step') != self.request or symbols.get('stimulus_ack') != self.ack:
                raise ValueError('PLIC evidence mailbox differs from ELF')
        self.started = 0
        self.waiting = deque()
        self.requests = deque()
        self.accesses = deque()
        self.pending_taken = None
        self.levels = None
        self.pc = cpu.elf.entry
        self.counts = Counter()

    def __getattr__(self, name):
        return getattr(self.cpu, name)

    def external_interrupt_event(self, event):
        kind = event['kind']
        self.counts[kind] += 1
        if kind == 'source':
            if self.started >= len(self.plan):
                raise ValueError('extra PLIC source event')
            plan = self.plan[self.started]
            if plan['kind'] != 'plic-level' or any(event.get(k) != plan[k] for k in ('source', 'level', 'step')):
                raise ValueError('PLIC source differs from stimulus plan')
            self.plic.set_level(event['source'], event['level'])
            self.started += 1
            self.requests.append(plan['step'])
            self.waiting.append((event['cycle'] + plan.get('settle_ticks', 0), plan['step']))
        elif kind == 'pins':
            observed = int(event['levels'], 16)
            expected = sum(1 << pin for context, pin in self.routes if self.plic.irq(context))
            if observed != expected:
                raise ValueError('PLIC pin routing differs from independent device state')
            self.levels = expected
        elif kind == 'ack':
            if not self.waiting:
                raise ValueError('acknowledgement has no served source event')
            due, step = self.waiting.popleft()
            if (event['cycle'] < due or event['step'] != step or int(event['value'], 16) != step
                    or int(event['address'], 16) != self.ack or event['bytes'] != 8):
                raise ValueError('invalid PLIC mailbox acknowledgement')
            value = step.to_bytes(8, 'little')
            if self.cpu.lib.rvw_write(self.cpu.handle, self.ack, value, 8):
                raise ValueError(self.cpu.error())
        elif kind == 'mmio':
            address, value, size = int(event['address'], 16), int(event['value'], 16), event['bytes']
            decoded = self.plic._decode(address, size)
            if event['write']:
                self.plic.write(address, value, size)
            else:
                expected = self.plic.read(address, size)
                if expected != value:
                    raise ValueError('PLIC accepted read differs from independent device model')
            if decoded[0] == 'claim':
                self.counts['complete' if event['write'] else 'claim'] += 1
            self.accesses.append((event['write'], address, size, value))
        elif kind == 'taken':
            cause = int(event['cause'], 16)
            pin = cause & ((1 << (self.cpu.platform.xlen - 1)) - 1)
            if self.pending_taken is not None or self.levels is None or not self.levels >> pin & 1:
                raise ValueError('interrupt taken without an asserted observed pin')
            self.pending_taken = cause

    def _read(self, address):
        value = ctypes.c_uint64()
        if self.cpu.lib.rvw_read_physical(self.cpu.handle, address, ctypes.byref(value)):
            raise ValueError(self.cpu.error())
        return value.value

    def step(self, interrupt=0, mmio=None):
        if mmio is not None:
            raise ValueError('external PLIC replay does not permit MMIO synchronization')
        if interrupt:
            if self.pending_taken != interrupt:
                raise ValueError('C2 interrupt has no matching taken boundary')
            self.pending_taken = None
        elif self.pending_taken is not None:
            raise ValueError('taken boundary was not followed by an interrupt trap')
        instruction = self._read(self.pc) & 0xffffffff
        injected = None
        if not interrupt and instruction & 0x7f == 3:
            immediate = instruction >> 20
            if immediate & 0x800:
                immediate -= 4096
            address = (self.cpu.regs[(instruction >> 15) & 31] + immediate) & ((1 << self.cpu.platform.xlen) - 1)
            if self.accesses and not self.accesses[0][0] and address == self.accesses[0][1]:
                injected = (address, self.accesses[0][3])
        # Pending-state CSR reads get checked pin values, not DUT read values.
        pending_read = instruction & 0x7f == 0x73 and instruction >> 20 in (0x344, 0x144)
        mask = sum(1 << pin for _, pin in self.routes)
        if pending_read:
            self.cpu.external_pending(mask, self.levels or 0)
        try:
            effect = self.cpu.step(interrupt=interrupt, mmio=injected)
        finally:
            if pending_read:
                self.cpu.external_pending(mask, 0)
        self.pc = effect['pc_next']
        if not effect['trap'] and (effect['mem_rmask'] or effect['mem_wmask']):
            address = effect['mem_addr']
            size = (effect['mem_rmask'] or effect['mem_wmask']).bit_count()
            if effect['mem_wmask'] and address == self.request:
                if not self.requests or self.requests.popleft() != effect['mem_wdata'] or size != 8:
                    raise ValueError('retired request differs from served stimulus step')
            try:
                self.plic._decode(address, size)
            except ValueError:
                return effect
            write = bool(effect['mem_wmask'])
            value = effect['mem_wdata'] if write else effect['mem_rdata']
            value &= (1 << (8 * size)) - 1
            if not self.accesses or self.accesses.popleft() != (write, address, size, value):
                raise ValueError('retired device access differs from accepted bus evidence')
        return effect

    def finish_external_interrupts(self):
        if self.started != len(self.plan) or self.waiting or self.requests or self.accesses or self.pending_taken or self.levels is None:
            raise ValueError('external interrupt evidence is incomplete')
        expected_levels = sum(1 << pin for context, pin in self.routes if self.plic.irq(context))
        if self.levels != expected_levels:
            raise ValueError('final PLIC pin evidence differs from independent state')
        return dict(schema='rvw.external-interrupts/1', status='checked', **self.counts)
