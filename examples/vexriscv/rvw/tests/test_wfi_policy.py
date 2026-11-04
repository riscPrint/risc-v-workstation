"""A legal early WFI completion must not need an illegal-instruction trap."""
import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest


def test_early_user_wfi_completion(monkeypatch):
    pytest.importorskip('cocotb')
    directory = Path(__file__).resolve().parents[2] / 'cocotb'
    monkeypatch.syspath_prepend(str(directory))
    spec = importlib.util.spec_from_file_location('wfi_policy_fixture', directory / 'test_wfi.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv('RVW_WFI_TRAP_BOUND', '8')
    dut = SimpleNamespace(reset=SimpleNamespace(value=0),
                          observed_privilege=SimpleNamespace(value=0),
                          observed_wfi=SimpleNamespace(value=1))

    class CompletedBus:
        def __init__(self, *_):
            self.traps = []
            self.retired = []

        async def pulse_reset(self):
            pass

        async def until(self, predicate):
            assert predicate()

        async def step(self):
            self.retired.append((0x80000000, 0x10500073, 0))

    monkeypatch.setattr(module, 'CoreBus', CompletedBus)
    monkeypatch.setattr(module, 'program', lambda *args: ({}, {'wait_start': 0x80000000}))
    asyncio.run(module.privilege_trap(dut, 0, 0))
