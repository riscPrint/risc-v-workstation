import importlib.util
from pathlib import Path
import pytest

pytestmark=pytest.mark.fast
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('hardfloat_runner',ROOT/'SpinalChecks/c2rtl/hardfloat.py')
example=importlib.util.module_from_spec(spec);spec.loader.exec_module(example)


def test_conversion_maps_invalid_and_overflow_to_nv():
    wrapper=example.wrapper('to-int')
    assert "integer_flags[2] | integer_flags[1],3'b000,integer_flags[0]" in wrapper
    assert 'signedOut(1\'b1)' in wrapper


@pytest.mark.parametrize('operation',list(example.MODELS))
def test_real_unit_wrapper_interfaces(operation):
    wrapper=example.wrapper(operation)
    assert 'module dut(' in wrapper and 'output [4:0] flags' in wrapper
    if operation in ('div','sqrt'):
        assert '.nReset(!reset)' in wrapper and '.inValid(start)' in wrapper and '.outValid(done)' in wrapper
    if operation=='fma':assert ".op(2'b00),.c(cr)" in wrapper
    if operation=='from-int':assert "iNToRecFN #(32,8,24)" in wrapper


def test_unknown_unit_is_refused():
    with pytest.raises(ValueError):example.wrapper('unknown')


def test_binary16_parameters_and_reference():
    w=example.wrapper('add',16)
    assert 'input [15:0] a,b,c' in w and 'addRecFN #(5,11)' in w
    assert "16'h7e00" in w and 'raw_result[14:10]' in w
    c=example.reference_source('fma',16)
    assert 'f16_mulAdd' in c and 'float16_t' in c and '32256ULL' in c
    assert 'float32_t' not in c and '2143289344ULL' not in c


def test_binary16_integer_conversion_widths():
    assert 'input [31:0] a,b,c' in example.wrapper('from-int',16)
    assert 'output [15:0] y' in example.wrapper('from-int',16)
    assert 'input [15:0] a,b,c' in example.wrapper('to-int',16)
    assert 'output [31:0] y' in example.wrapper('to-int',16)
    assert 'i32_to_f16' in example.reference_source('from-int',16)
    assert 'f16_to_i32' in example.reference_source('to-int',16)
