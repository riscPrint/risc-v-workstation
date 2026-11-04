"""Clock pause/restart on real core RTL. No minimum WFI sleep duration."""
import os
from pathlib import Path
import subprocess
import tempfile
import cocotb
from cocotb.triggers import Timer
from rvw.cosim.elf import Elf
from core_bus import CoreBus


def program(code, privilege=3, tw=0, masked=False):
    source = Path(__file__).resolve().parent.parent / 'rvw/programs/wfi-clock.S'
    with tempfile.TemporaryDirectory(prefix='rvw-wfi-') as tmp:
        elf = Path(tmp) / 'wfi'
        subprocess.run([os.environ.get('RISCV_GCC', 'riscv64-unknown-elf-gcc'),
            '-march=rv32im_zicsr', '-mabi=ilp32', '-nostdlib', '-nostartfiles', '-static',
            '-T', str(source.with_name('link.ld')), f'-DIRQ_CODE={code}',
            f'-DPRIV={privilege}', f'-DTW={tw}', *(['-DMASK_GLOBAL'] if masked else []),
            '-o', str(elf), str(source)], check=True, capture_output=True)
        image = Elf(elf)
    words = {}
    for address, data, size in image.segments:
        data += bytes(size - len(data))
        for offset in range(0, len(data), 4):
            words[address + offset] = int.from_bytes(data[offset:offset + 4], 'little')
    return words, image.symbols


def snapshot(d):
    # Ignore combinational input synchronizers. Check retained architectural state.
    return tuple(int(getattr(d, name).value) for name in
                 ('observed_privilege', 'observed_status', 'observed_epc', 'rvfi_order', 'rvfi_pc_rdata'))


async def wake(dut, code, pin, masked=False):
    words, symbols = program(code, masked=masked)
    b = CoreBus(dut, words)
    await b.pulse_reset()
    dut.reset.value = 0
    await b.until(lambda: bool(int(dut.observed_wfi.value)))
    # WFI may return early. Arrival at WFI, not a sleep duration, selects the pause.
    before = snapshot(dut)
    assert not b.traps
    dut.clk.value = 0
    getattr(dut, pin).value = 1
    await Timer(100, unit='ns')  # IRQ changes while there are no clock edges
    assert snapshot(dut) == before
    if masked:
        # Local enable must wake WFI even when global MIE prevents trap delivery.
        await b.until(lambda: any(insn == 0x10500073 for _, insn, _ in b.retired))
        for _ in range(20):
            await b.step()
        assert not b.traps
        assert int(dut.observed_status.value) & 8 == 0
    else:
        await b.until(lambda: bool(b.traps))
        assert b.traps == [0x80000000 | code]
        assert symbols['wait_start'] <= int(dut.observed_epc.value) < symbols['wait_end']
        await b.until(lambda: any(a == symbols['tohost'] for a, _ in b.stores))
        assert (symbols['tohost'], 1) in b.stores
        assert any(symbols['handler'] <= pc for pc, _, _ in b.retired)
        assert int(dut.observed_status.value) & 8 == 0


@cocotb.test()
async def timer_across_clock_stop(dut):
    await wake(dut, 7, 'timerInterrupt')


@cocotb.test()
async def software_across_clock_stop(dut):
    await wake(dut, 3, 'softwareInterrupt')


@cocotb.test()
async def external_across_clock_stop(dut):
    await wake(dut, 11, 'externalInterrupt')


@cocotb.test()
async def timer_wake_with_global_interrupts_masked(dut):
    await wake(dut, 7, 'timerInterrupt', masked=True)


async def privilege_trap(dut, privilege, tw):
    words, symbols = program(7, privilege, tw)
    b = CoreBus(dut, words)
    await b.pulse_reset()
    dut.reset.value = 0
    await b.until(lambda: bool(b.traps) or bool(int(dut.observed_wfi.value)))
    assert int(dut.observed_privilege.value) in (privilege, 3)
    if tw and not b.traps:
        assert int(dut.observed_status.value) & (1 << 21), 'TW write was not retained'
    # The spec permits completion before the implementation-specific timeout.
    bound = int(os.environ['RVW_WFI_TRAP_BOUND'])
    assert bound > 0, 'the qualified implementation bound must be positive'
    for _ in range(bound):
        if b.traps:
            break
        if any(insn == 0x10500073 for _, insn, _ in b.retired):
            assert not b.traps
            return
        await b.step()
    if not b.traps and any(insn == 0x10500073 for _, insn, _ in b.retired):
        return
    assert b.traps == [2], (privilege, tw, b.traps)
    assert int(dut.observed_epc.value) == symbols['wait_start']
    await b.until(lambda: bool(b.stores))
    assert (symbols['tohost'], 1) in b.stores


# No qualified trap timeout is available for this example. A skipped test is
# inconclusive in C3, never passing privilege coverage. Do not invent a bound.
@cocotb.test(skip='RVW_WFI_TRAP_BOUND' not in os.environ)
async def user_wfi_bounded_trap(dut):
    await privilege_trap(dut, 0, 0)


@cocotb.test()
async def supervisor_wfi_tw_readonly_zero(dut):
    words, symbols = program(7, 1, 1)
    b = CoreBus(dut, words)
    await b.pulse_reset()
    dut.reset.value = 0
    await b.until(lambda: bool(b.traps) or bool(int(dut.observed_wfi.value)))
    assert not b.traps
    assert int(dut.observed_privilege.value) == 1
    # This configuration implements only the legal WARL value TW=0.
    assert int(dut.observed_status.value) & (1 << 21) == 0
    dut.timerInterrupt.value = 1
    await b.until(lambda: bool(b.traps))
    assert b.traps == [0x80000007]
    await b.until(lambda: bool(b.stores))
    assert (symbols['tohost'], 1) in b.stores
