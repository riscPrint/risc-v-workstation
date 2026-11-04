"""Independent register expectations. No Linux RTL boot claim."""
import importlib.util
from pathlib import Path
import pytest
from rvw.cosim.devices import Ns16550


def platform():
    path = Path(__file__).resolve().parents[3] / 'examples/qemu-linux/devices.py'
    spec = importlib.util.spec_from_file_location('linux_devices', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.LinuxDevices()


def test_uart_registers_divisor_output_and_interrupt_ack():
    u = Ns16550()
    assert u.read(5) == 0x60 and u.read(2) == 1
    u.write(3, 0x80)
    u.write(0, 12)
    u.write(1, 3)
    assert (u.read(0), u.read(1)) == (12, 3)
    u.write(3, 3)
    u.write(7, 0xa5)
    assert u.read(7) == 0xa5
    u.write(1, 2)
    assert u.irq() and u.read(2) == 2
    assert not u.irq() and u.read(2) == 1
    u.write(0, 65)
    assert u.output == b'A' and u.irq()
    u.reset()
    assert not u.output and not u.irq() and u.read(3) == 0


def test_linux_uart_plic_claim_complete_and_timer_levels():
    d = platform()
    assert d.irq() == 0
    d.write(0x0c000028, 3, 4)  # UART source 10 priority.
    d.write(0x0c002080, 1 << 10, 4)  # Supervisor context enable.
    d.write(0x10000001, 2, 1)
    assert d.irq() == 0x200
    assert d.read(0x0c201004, 4) == 10
    assert d.irq() == 0
    assert d.read(0x10000002, 1) == 2  # Clear UART TX pending.
    d.write(0x0c201004, 10, 4)
    assert d.irq() == 0
    d.write(0x02004000, 5, 8)
    d.timer.tick(5)
    assert d.irq() == 0x80
    d.write(0x02000000, 1, 4)
    assert d.irq() == 0x88
    d.reset()
    assert d.irq() == 0


def test_unsupported_effects_fail_closed():
    d = platform()
    for address, size in [(0x10000000, 4), (0x10000000, 1), (0x10000006, 1), (0x40000000, 4)]:
        with pytest.raises(ValueError):
            d.read(address, size)
    with pytest.raises(ValueError):
        d.write(0x10000001, 1, 1)
    with pytest.raises(ValueError):
        d.write(0x10000002, 1, 1)
