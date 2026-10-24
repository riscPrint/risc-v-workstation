"""ELF disassembly indexed by program counter (objdump)."""
from __future__ import annotations

import os
import re
import shutil
from rvw.common.proc import run_group
from dataclasses import dataclass

OBJDUMP_CANDIDATES = ["riscv64-unknown-elf-objdump", "riscv64-linux-gnu-objdump", "riscv32-unknown-elf-objdump",
                      "llvm-objdump"]
TOOLCHAIN_DIRS = ["/opt/homebrew/opt/riscv-gnu-toolchain/bin", "/opt/riscv/bin"]


def find_objdump(environment=None) -> str | None:
    environment = os.environ if environment is None else environment
    env = environment.get("RISCV_OBJDUMP")
    if env:
        return env
    for name in OBJDUMP_CANDIDATES:
        p = shutil.which(name, path=environment.get("PATH"))
        if p:
            return p
        for d in TOOLCHAIN_DIRS:
            c = os.path.join(d, name)
            if os.access(c, os.X_OK):
                return c
    return None


@dataclass
class Line:
    pc: int
    raw: str       # instruction bytes as printed (e.g. "00000297" or "4501")
    text: str      # "auipc t0,0x0"
    func: str      # enclosing symbol


class Disasm:
    def __init__(self, elf: str | None, *, capture=None, environment=None):
        self.by_pc: dict[int, Line] = {}
        self.funcs: list[tuple[int, str]] = []
        self.error: str | None = None
        if not elf or not os.path.exists(elf):
            self.error = f"ELF not found: {elf}"
            return
        exe = find_objdump(environment)
        if not exe:
            self.error = "no RISC-V objdump found (set RISCV_OBJDUMP)"
            return
        exe = str(capture.tool(exe).path) if capture is not None else exe
        result = run_group([exe, '-d', elf], capture=True, timeout=60, env=environment)
        if result.timed_out or result.returncode:
            self.error = f"objdump failed: {(result.stderr or '')[:200]}"
            return
        out = result.stdout
        func = "?"
        frx = re.compile(r"^([0-9a-f]+) <([^>]+)>:")
        irx = re.compile(r"^\s*([0-9a-f]+):\s+([0-9a-f]+(?: [0-9a-f]+)*)\s+(.*)$")
        for line in out.splitlines():
            m = frx.match(line)
            if m:
                func = m.group(2)
                self.funcs.append((int(m.group(1), 16), func))
                continue
            m = irx.match(line)
            if m:
                pc = int(m.group(1), 16)
                self.by_pc[pc] = Line(pc, m.group(2).replace(" ", ""), " ".join(m.group(3).split()), func)
        self.funcs.sort()

    def at(self, pc: int) -> Line | None:
        return self.by_pc.get(pc)

    def text(self, pc: int) -> str:
        l = self.by_pc.get(pc)
        return f"{l.text}" if l else "(not in ELF)"

    def func(self, pc: int) -> str:
        l = self.by_pc.get(pc)
        if l:
            return l.func
        import bisect
        i = bisect.bisect_right(self.funcs, (pc, "\uffff")) - 1
        return self.funcs[i][1] if i >= 0 else "?"
