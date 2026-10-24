"""Generate bounded C2 traces from Spike's independently executing hart."""
import json
import os
from pathlib import Path
import tempfile
from .spike import Spike
from .trace import record


def generate(elf, out, platform, limit=1000000, *, shim, verify=lambda: None,
             elf_source=None):
    model = Spike(platform, elf, shim=shim)
    count, status = 0, "limit"
    after_trap = False
    # A unique temporary in the output directory: concurrent generations and a user's own
    # files never share it, and the final rename stays on one file system.
    fd, name = tempfile.mkstemp(prefix=Path(out).name + ".", suffix=".partial", dir=Path(out).resolve().parent)
    temporary = Path(name)
    os.chmod(fd, 0o644)   # mkstemp creates 0600; a trace is an ordinary readable file
    try:
        with os.fdopen(fd, "w") as stream:
            def emit(obj):
                stream.write(json.dumps(obj, separators=(",", ":")) + "\n")
            emit({"schema": "rvw.rvfi/1", "xlen": platform.xlen, "isa": platform.isa,
                  "core": platform.name, "config": "reference", "elf": elf_source or str(Path(elf).resolve())})
            for i in range(limit):
                e = model.step()
                emit(record(e, i, intr=after_trap, xlen=platform.xlen))
                after_trap = bool(e["trap"])
                count += 1
                if e["trap"]:
                    emit({"event": "trap", "cycle": i, "cause": hex(e["cause"]),
                          "tval": hex(e["tval"]), "intr": bool(e["intr"])})
                tohost = model.elf.symbols.get("tohost")
                if tohost and e["mem_addr"] == tohost and e["mem_wmask"] and e["mem_wdata"] & 1:
                    status = "pass" if e["mem_wdata"] == 1 else "fail"
                    break
                if e["halted"]:
                    status = "halt"
                    break
            if status != "limit":
                emit({"event": "end", "cycle": count-1, "status": status})
        verify()
        temporary.replace(out)   # a failed generation leaves an existing trace unchanged
        return {"schema": "rvw.cosim/1", "status": "generated", "instructions": count,
                "termination": status, "trace": str(Path(out).resolve())}
    finally:
        model.close()
        temporary.unlink(missing_ok=True)
