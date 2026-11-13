"""The interop script must set instruction breakpoints, not function breakpoints."""
import runpy
import sys
from types import SimpleNamespace

import pytest
from rvw.debug.interop import SCRIPT

pytestmark = pytest.mark.fast


@pytest.mark.parametrize("stop", ["break *target", "hbreak *target"])
def test_breakpoint_uses_instruction_address(monkeypatch, stop):
    commands = []
    class Stop(Exception):
        pass
    def execute(command, **kwargs):
        commands.append(command)
        # Reject the original bug before it reaches the target.
        assert command not in ("break target", "hbreak target")
        if command == stop:
            raise Stop
        return ""
    class Value(int):
        type = SimpleNamespace(sizeof=4)
    monkeypatch.setitem(sys.modules, "gdb", SimpleNamespace(
        execute=execute, parse_and_eval=lambda expr: Value(0), VERSION="test", error=RuntimeError))
    monkeypatch.setenv("RVW_ELF", "fixture.elf")
    monkeypatch.setenv("RVW_OPENOCD_PIPE", "openocd")
    monkeypatch.setenv("RVW_FIRST_WORD", "13000000")
    with pytest.raises(Stop):
        runpy.run_path(str(SCRIPT))
    assert stop in commands
