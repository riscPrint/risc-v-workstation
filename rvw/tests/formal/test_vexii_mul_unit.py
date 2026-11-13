"""Reference-domain checks for the real VexiiRiscv multiplier helpers."""
import ctypes
import importlib.util
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('vexii_mul_unit', ROOT/'examples/vexiiriscv/formal/mul-unit.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@pytest.mark.fast
@pytest.mark.parametrize('op,signs', [('mul',(True,True)),('mulh',(True,True)),
                                     ('mulhu',(False,False)),('mulhsu',(True,False))])
def test_operation_signedness(op, signs):
    assert runner.signed_operands(op) == signs


@pytest.mark.fast
@pytest.mark.parametrize('op', ['divu','unknown'])
def test_unknown_operations_are_refused(op):
    with pytest.raises(ValueError):
        runner.adapter(op, 32)


@pytest.mark.fast
@pytest.mark.parametrize('width', [0,33])
def test_bad_projection_is_refused(width):
    with pytest.raises(ValueError):
        runner.adapter('mul', width)


@pytest.mark.fast
def test_full_word_projection_keeps_each_operand():
    assert runner.projection('a', True, 32) == 'a'
    assert runner.projection('b', False, 32) == 'b'


@pytest.mark.slow
@pytest.mark.skipif(not shutil.which('cc'), reason='C compiler')
@pytest.mark.parametrize('op', runner.OPS)
def test_projected_model_exhaustive_against_python(tmp_path, op):
    source = tmp_path/'reference.c'
    source.write_text(runner.model(ROOT, op, 8))
    library = tmp_path/'reference.so'
    subprocess.run(['nice','-n','10','cc','-shared','-fPIC','-O2',str(source),'-o',str(library)],check=True,capture_output=True)
    ref = ctypes.CDLL(str(library)).reference
    ref.argtypes = [ctypes.c_uint64,ctypes.c_uint64,ctypes.c_uint64,ctypes.c_uint8,
                    ctypes.POINTER(ctypes.c_uint8)]
    ref.restype = ctypes.c_uint64
    sa,sb = runner.signed_operands(op)
    flags=ctypes.c_uint8()
    for a in range(256):
        for b in range(256):
            aa=a-256 if sa and a>=128 else a
            bb=b-256 if sb and b>=128 else b
            value=aa*bb
            expected=(value if op=='mul' else value>>32)&0xffffffff
            assert ref(a,b,0,0,ctypes.byref(flags))==expected,(op,a,b)
            assert flags.value==0
