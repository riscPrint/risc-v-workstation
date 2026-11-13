import json
from pathlib import Path
import pytest
from rvw.formal.csr import generate

pytestmark=pytest.mark.fast


def test_vexii_selection_keeps_absent_csr_and_unknown_scratch_reset(tmp_path):
    root=Path(__file__).resolve().parents[2]
    result=generate(root/'examples/vexiiriscv/csr.json',tmp_path/'generated')
    assert result['csrs']==2
    model=json.loads((tmp_path/'generated/model.json').read_text())
    rows={r['name']:r for r in model['csrs']}
    assert rows['mscratch']['address']==0x340
    assert rows['mscratch']['reset_known'] is False
    assert rows['mscratch']['assembly_safe'] is True
    assert rows['sscratch']['present'] is False
    assert all((tmp_path/'generated'/(name+'.S')).is_file() for name in rows)
