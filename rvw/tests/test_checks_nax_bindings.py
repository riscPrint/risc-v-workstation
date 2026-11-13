"""Check the project-owned NaxRiscv declarations without a native core build."""
import json
from pathlib import Path
import pytest
from rvw.formal.micro_checks import generate

pytestmark = pytest.mark.fast


def test_nax_declares_nine_generatable_rules(tmp_path):
    source=Path(__file__).resolve().parents[2]/'examples/naxriscv/rvw/micro-checks.json'
    spec=json.loads(source.read_text())
    result=generate(spec,tmp_path/'generated')
    assert result['complete']
    assert len(result['rules'])==9
    assert {r['kind'] for r in result['rules']}=={'counter_bounds','pipeline','rob_pointers','freelist_ghost','store_forward_window'}
    assert all(r['status']=='generated' for r in result['rules'])
