"""CPU environment services shared by project cocotb/pyuvm adapters.

Protocol adapters own pin handshakes. This module owns memory, stimulus and
retirement checks. Signal names belong to the project's binding dictionary.
"""
from dataclasses import dataclass
import random


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
        offset = self.offset(address, size)
        return int.from_bytes(self.data[offset:offset+size], 'little')

    def write(self, address, value, size, mask=None):
        offset = self.offset(address, size)
        mask = (1 << size) - 1 if mask is None else mask
        if value < 0 or value >= 1 << (size*8) or mask < 0 or mask >= 1 << size:
            raise ValueError('data or mask exceeds transfer width')
        for i in range(size):
            if mask & (1 << i):
                self.data[offset+i] = (value >> (8*i)) & 255


@dataclass(frozen=True)
class MemoryReply:
    data: int
    error: bool
    wait_cycles: int


class CpuMemory:
    def __init__(self, base, size, *, seed=1, max_wait=3, fetch_errors=()):
        if type(max_wait) is not int or max_wait < 0:
            raise ValueError('max_wait must be a nonnegative integer')
        self.memory = Memory(base, size)
        self.random = random.Random(seed)
        self.max_wait = max_wait
        self.fetch_errors = set(fetch_errors)
        self.transfers = 0

    def preload(self, elf):
        # Check all segments before changing shared instruction/data memory.
        for address, data, memsz in elf.segments:
            self.memory.offset(address, memsz)
        for address, data, memsz in elf.segments:
            offset = self.memory.offset(address, memsz)
            self.memory.data[offset:offset+memsz] = data + bytes(memsz-len(data))

    def access(self, address, *, instruction=False, write=False, data=0, mask=15):
        delay = self.random.randrange(self.max_wait + 1)
        self.transfers += 1
        if address % 4 or (instruction and address in self.fetch_errors):
            return MemoryReply(0, True, delay)
        try:
            self.memory.offset(address, 4)
        except ValueError:
            return MemoryReply(0, True, delay)
        if instruction and write:
            raise ValueError('instruction port cannot write')
        if write:
            self.memory.write(address, data, 4, mask)
        return MemoryReply(self.memory.read(address, 4), False, delay)


class CpuCoverage:
    def __init__(self):
        self.opcodes, self.csrs, self.interrupts, self.exceptions = set(), set(), set(), set()
        self.samples = 0

    def sample(self, record):
        insn = record['insn']
        self.opcodes.add(insn & 127)
        if insn & 127 == 0x73 and (insn >> 12) & 7:
            self.csrs.add(insn >> 20)
        self.interrupts.add(bool(record['intr']))
        self.exceptions.add(bool(record['trap']))
        self.samples += 1

    def report(self):
        return dict(samples=self.samples, opcodes=sorted(self.opcodes), csrs=sorted(self.csrs),
                    interrupts=sorted(self.interrupts), exceptions=sorted(self.exceptions))


class CpuScoreboard:
    """Check scalar retirement fields against a separately stepped reference.

    The project supplies a captured Spike instance or another strict reference.
    Handler entry, debug and FP require an extended comparator. Optional GPR
    and CSR snapshots describe architectural state after retirement.
    No DUT value is copied into reference state.
    """
    fields = 'pc pc_next insn mode rd rd_wdata mem_addr mem_rmask mem_wmask mem_rdata mem_wdata trap mem_fault'.split()

    def __init__(self, reference):
        self.reference, self.checks = reference, 0
        self.coverage = CpuCoverage()
        self.after_trap = False

    def observe(self, record):
        required = self.fields + 'order rs1 rs1_rdata rs2 rs2_rdata intr halt'.split()
        if any(k not in record for k in required):
            raise ValueError('incomplete scalar RVFI record')
        if record['order'] != self.checks:
            raise AssertionError('retirement gap or duplicate')
        # RVFI intr marks the first instruction of any trap handler. After a
        # retired synchronous trap the reference is already in the handler, so
        # that entry is ordinary. Without a preceding trap it is an
        # asynchronous interrupt, which needs an extended comparator.
        handler_entry = record['intr'] and self.after_trap
        if (record['intr'] and not handler_entry) or record['halt'] or (record.get('csr_state') and not callable(getattr(self.reference,'csr_snapshot',None))):
            raise ValueError('unsupported:cpu_extended_observation')
        expected = self.reference.step()
        if expected.get('intr') or expected.get('fd_valid'):
            raise ValueError('unsupported:cpu_reference_effect')
        for key in self.fields:
            if key == 'rd_wdata' and expected['rd'] == 0:
                continue
            if key == 'mem_addr' and not (expected['mem_rmask'] or expected['mem_wmask']):
                if not (record['mem_rmask'] or record['mem_wmask']):
                    continue
            mask = (1 << 64)-1
            if key in ('mem_rdata', 'mem_wdata'):
                lanes = expected['mem_rmask' if key == 'mem_rdata' else 'mem_wmask']
                mask = sum(255 << (i*8) for i in range(8) if lanes & (1 << i))
            if record[key] & mask != expected[key] & mask:
                raise AssertionError(f'SPIKE_MISMATCH:{key} order={record["order"]} pc={record["pc"]:#x} '
                                     f'insn={record["insn"]:#010x} actual={record[key] & mask:#x} '
                                     f'expected={expected[key] & mask:#x}')
        for name in ('rs1', 'rs2'):
            index = record[name]
            if not 0 <= index < 32 or record[name+'_rdata'] != expected['before'][index]:
                raise AssertionError(f'SPIKE_MISMATCH:{name}_rdata')
        if 'gpr_state' in record and record['gpr_state'] != expected['regs']:
            raise AssertionError('SPIKE_MISMATCH:gpr_state')
        if record.get('csr_state'):
            values = self.reference.csr_snapshot(list(record['csr_state']))
            if values != record['csr_state']:
                raise AssertionError('SPIKE_MISMATCH:csr_state')
        self.coverage.sample(record)
        self.after_trap = bool(record['trap'])
        self.checks += 1

    def finish(self, expected_retirements):
        if expected_retirements < 1 or self.checks != expected_retirements:
            raise AssertionError('missing CPU retirement checks')


def spike_reference(platform, elf, work, shim=None):
    """A captured Spike instance for CpuScoreboard. `platform` is a cosim
    platform JSON path. The shim defaults to $RVW_SPIKE_SHIM or this checkout's
    Cosim build; its bytes and linked Spike are captured under `work`."""
    import os
    from pathlib import Path
    from rvw.common.capture import Capture
    from rvw.cosim.platform import Platform
    from rvw.cosim.spike import Spike, capture_shim
    root = Path(__file__).resolve().parents[4]
    shim = shim or os.environ.get('RVW_SPIKE_SHIM') or root / 'Cosim/build/librvw_spike.so'
    captured = capture_shim(Capture(Path(work) / 'reference-inputs'), shim)
    return Spike(Platform.load('project', platform), str(elf), shim=captured)


async def monitor(dut, bindings, scoreboard, *, retirements, max_cycles):
    """Read one scalar RVFI channel at falling edges, after the active edge."""
    from cocotb.triggers import FallingEdge, ReadOnly
    clock = getattr(dut, bindings['clock'])
    for _ in range(max_cycles):
        await FallingEdge(clock)
        await ReadOnly()
        if int(getattr(dut, bindings['reset_n']).value) and int(getattr(dut, bindings['valid']).value):
            record = {name: int(getattr(dut, signal).value) for name, signal in bindings['fields'].items()}
            scoreboard.observe(record)
            if scoreboard.checks == retirements:
                scoreboard.finish(retirements)
                return
    raise AssertionError('CPU retirement watchdog expired')


class CpuControls:
    """Project callbacks drive reset, IRQ levels and debug requests."""
    def __init__(self, wait_cycles, reset, irq, debug, *, seed=1):
        self.wait_cycles, self.drive_reset = wait_cycles, reset
        self.drive_irq, self.drive_debug = irq, debug
        self.random = random.Random(seed)

    async def reset(self, cycles=5):
        if cycles < 1:
            raise ValueError('positive reset cycles required')
        self.drive_irq(0); self.drive_debug(0); self.drive_reset(True)
        await self.wait_cycles(cycles)
        self.drive_reset(False)

    async def random_requests(self, count, allowed_irqs, max_gap=8):
        if count < 1 or max_gap < 1 or not 0 < allowed_irqs < 2**32:
            raise ValueError('positive count/gap and a 32-bit project IRQ mask required')
        try:
            for _ in range(count):
                await self.wait_cycles(self.random.randint(1,max_gap))
                cycles = self.random.randint(1,3)
                if self.random.randrange(2):
                    self.drive_debug(1)
                    await self.wait_cycles(cycles)
                    self.drive_debug(0)
                else:
                    levels = self.random.getrandbits(32) & allowed_irqs
                    self.drive_irq(levels or (allowed_irqs & -allowed_irqs))
                    await self.wait_cycles(cycles)
                    self.drive_irq(0)
        finally:
            self.drive_irq(0); self.drive_debug(0)
