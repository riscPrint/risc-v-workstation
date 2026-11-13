"""Map-driven DT generation. Full Linux boot is a separate native recipe."""
import importlib.util
from pathlib import Path
import shutil
import pytest


def test_linux_tree_uses_soc_ram_and_project_interrupt_bindings(tmp_path):
    if not shutil.which('dtc'): pytest.skip('dtc required')
    folder = Path(__file__).resolve().parents[2] / 'examples/qemu-linux'
    spec = importlib.util.spec_from_file_location('sim_soc_boot', folder/'sim-soc-boot.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    out = tmp_path/'generated'
    module.tree(folder/'sim-soc.json', out)
    tree = (out/'soc.dts').read_text()
    assert '0x80000000 0x0 0x8000000' in tree
    assert 'interrupts-extended = <&intc 11 &intc 9>' in tree
    assert (out/'soc.dtb').read_bytes()[:4] == bytes.fromhex('d00dfeed')
