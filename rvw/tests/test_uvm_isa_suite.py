"""ISA discovery includes every built program in the supported profiles."""
import importlib.util
from pathlib import Path
import pytest
pytestmark=pytest.mark.fast
spec=importlib.util.spec_from_file_location('isa_suite',Path(__file__).resolve().parents[2]/'Uvm/examples/vexriscv/isa_suite.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_discovery_includes_misaligned_and_m_extension_without_dump_files(tmp_path):
    names=['rv32ui-p-add','rv32ui-p-ma_data','rv32um-p-div']
    for name in names: (tmp_path/name).write_bytes(b'\x7fELFdata')
    (tmp_path/'rv32ui-p-add.dump').write_text('dump')
    (tmp_path/'rv64ui-p-add').write_bytes(b'\x7fELFdata')
    assert [p.name for p in module.programs(tmp_path)]==sorted(names)
    assert module.programs(tmp_path/'absent')==[]
