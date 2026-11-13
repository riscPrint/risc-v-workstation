"""Check scope of the project-owned arithmetic adapters."""
import importlib.util
from pathlib import Path
import pytest
pytestmark=pytest.mark.fast
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('vex_mul',ROOT/'examples/vexriscv/formal/mul-smoke.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def test_signed_high_product_keeps_rv32_selection():
    text=m.product_adapter('mulh',8,66)
    assert 'p[63:32]' in text
    assert 'a[7]' in text and 'b[7]' in text
    assert '.a33({aa[31],aa})' in text


def test_mixed_product_signs_only_first_operand():
    text=m.product_adapter('mulhsu',8,66)
    assert 'a[7]' in text and 'b[7]' not in text
    assert ".b33({1'b0,bb})" in text
    ref=m.reference('mulhsu',8)
    assert 'rvw_m(2,32,a,b)' in ref
    assert 'a & 255ULL' in ref and 'b & 255ULL' in ref


def test_full_width_is_not_narrowed():
    assert m.operand('a',32,True)=='a'
    assert 'p[31:0]' in m.product_adapter('mul',32,66)


def test_divider_domain_extension_matches_signedness():
    spec=importlib.util.spec_from_file_location('vex_div',ROOT/'examples/vexriscv/formal/div-smoke.py')
    div=importlib.util.module_from_spec(spec);spec.loader.exec_module(div)
    assert div.operand('a',8,True)==m.operand('a',8,True)
    assert div.operand('b',8,False)==m.operand('b',8,False)
    assert 'active && !raw_done' in div.adapter('div','full')
