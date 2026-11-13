"""Scope and model bindings for the real VexiiRiscv divider example."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('vexii_div_unit', ROOT / 'examples/vexiiriscv/formal/div-unit.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@pytest.mark.fast
@pytest.mark.parametrize('operation', ['div', 'rem', 'unknown'])
def test_signed_or_unknown_operations_are_not_silently_unsigned(operation):
    with pytest.raises(ValueError):
        runner.adapter(operation, 'full', 32)


@pytest.mark.fast
@pytest.mark.parametrize('width', [0, -1, 33])
def test_invalid_operand_projection_is_refused(width):
    with pytest.raises(ValueError):
        runner.adapter('divu', 'full', width)


@pytest.mark.fast
def test_projection_keeps_full_result_and_uses_same_model_domain():
    wrapper = runner.adapter('remu', 'full', 8)
    assert 'output [31:0] y' in wrapper
    assert "io_cmd_payload_a(a & 32'hff)" in wrapper
    assert "io_cmd_payload_b((b & 32'hff))" in wrapper
    text = runner.model(ROOT, 'remu', 'full', 8)
    assert '32, (a & 255ULL), (b & 255ULL))' in text


@pytest.mark.fast
def test_zero_divisor_applies_to_both_actual_unit_and_reference():
    wrapper = runner.adapter('divu', 'zero', 32)
    assert ".io_cmd_payload_b(32'd0)" in wrapper
    assert '32, (a & 4294967295ULL), 0ULL)' in runner.model(ROOT, 'divu', 'zero', 32)


@pytest.mark.fast
def test_default_core_divider_can_be_selected():
    text = runner.adapter('divu', 'full', 32, 'DivRadix')
    assert 'DivRadix unit0' in text and 'DivRadix2 unit0' not in text


@pytest.mark.fast
def test_unknown_divider_is_refused():
    with pytest.raises(ValueError):
        runner.adapter('divu', 'full', 32, 'unknown')
