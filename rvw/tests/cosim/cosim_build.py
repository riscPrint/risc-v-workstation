"""Build helper for cosim tests (a uniquely named module: `conftest` names clash between test folders)."""
import os
from pathlib import Path
import shutil
import subprocess
import pytest

def _build(tmp_path_factory, source, march="rv64ima_zicsr_zicntr_zihpm", mabi="lp64"):
    library = Path(__file__).resolve().parents[3] / "Cosim/build/librvw_spike.so"
    if not library.exists() and not os.environ.get("RVW_SPIKE_SHIM"):
        pytest.skip("build the native shim with Cosim/build.sh")
    compiler = os.environ.get("RISCV_GCC") or shutil.which("riscv64-unknown-elf-gcc")
    if not compiler:
        local = Path("/opt/homebrew/opt/riscv-gnu-toolchain/bin/riscv64-unknown-elf-gcc")
        if local.exists():
            compiler = str(local)
    if not compiler:
        pytest.skip("RISC-V GCC not available")
    out = tmp_path_factory.mktemp("cosim") / (source.stem + ".elf")
    subprocess.run([compiler, "-nostdlib", "-nostartfiles", "-march=" + march, "-mabi=" + mabi,
                    "-Wl,-T," + str(Path(__file__).with_name("program.ld")), "-Wl,--no-relax", "-Wl,--build-id=none", str(source),
                    "-o", str(out)], check=True, capture_output=True)
    return out


