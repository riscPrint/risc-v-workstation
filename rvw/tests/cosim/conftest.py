import os
from pathlib import Path
import shutil
import subprocess
import pytest
from rvw.cosim.platform import Platform


@pytest.fixture(scope="session")
def platform():
    return Platform.load("boom")


from cosim_build import _build  # noqa: E402
@pytest.fixture(scope="session")
def elf(tmp_path_factory, platform):
    return _build(tmp_path_factory, Path(__file__).with_name("program.S"))


@pytest.fixture(scope="session")
def umode_elf(tmp_path_factory, platform):
    return _build(tmp_path_factory, Path(__file__).with_name("program_umode.S"))


@pytest.fixture(scope="session")
def traps_elf(tmp_path_factory, platform):
    return _build(tmp_path_factory, Path(__file__).with_name("program_traps.S"))


@pytest.fixture(scope="session")
def csr_elf(tmp_path_factory, platform):
    return _build(tmp_path_factory, Path(__file__).with_name("program_csr.S"))


@pytest.fixture(scope="session")
def irq_elf(tmp_path_factory, platform):
    return _build(tmp_path_factory, Path(__file__).with_name("program_irq.S"))


@pytest.fixture(scope="session")
def sail():
    """Sail RISC-V simulator: RVW_SAIL, else the reference checkout next to this repository."""
    found = os.environ.get("RVW_SAIL") or shutil.which("sail_riscv_sim")
    if not found:
        local = Path(__file__).resolve().parents[4] / "ref/sail/sail-riscv-Mac-arm64/bin/sail_riscv_sim"
        found = str(local) if local.exists() else None
    if not found:
        pytest.skip("Sail not available (set RVW_SAIL)")
    return found


@pytest.fixture(scope="session")
def mip_elf(tmp_path_factory, platform):
    return _build(tmp_path_factory, Path(__file__).with_name("program_mip.S"))


@pytest.fixture(scope="session")
def sail_elf(tmp_path_factory, platform):
    return _build(tmp_path_factory, Path(__file__).with_name("program_sail.S"), march="rv64imac_zicsr")


@pytest.fixture(scope="session")
def outside_ram_elf(tmp_path_factory, platform):
    return _build(tmp_path_factory, Path(__file__).with_name("program_outside_ram.S"))


@pytest.fixture(scope="session")
def fetch_fault_elf(tmp_path_factory, platform):
    return _build(tmp_path_factory, Path(__file__).with_name("program_fetch_fault.S"))


@pytest.fixture(scope="session")
def ssip_elf(tmp_path_factory, platform):
    return _build(tmp_path_factory, Path(__file__).with_name("program_ssip.S"))


@pytest.fixture(scope="session")
def seip_elf(tmp_path_factory, platform):
    return _build(tmp_path_factory, Path(__file__).with_name("program_seip.S"))


@pytest.fixture(scope="session")
def rv32_cfp_elf(tmp_path_factory):
    return _build(tmp_path_factory, Path(__file__).with_name("program_rv32_cfp.S"),
                  march="rv32imafdc_zicsr", mabi="ilp32d")
