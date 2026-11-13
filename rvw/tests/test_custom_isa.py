"""Custom encoding, independent vectors and compiled software hooks."""
from copy import deepcopy
import json
from pathlib import Path
import runpy
import shutil
import subprocess

import pytest

from rvw.formal.custom_isa import decode, encode, expression, generate, load


def spec():
    return dict(schema='rvw.custom-isa/1', version='1.0.0', xlen=32, instructions=[
        dict(name='xadd', mask='0xfe00707f', match='0x0000000b', operands=['rd','rs1','rs2'],state=[],
             effects={'memory':'none','trap':'none','pc':'next'},result=['add','rs1','rs2'],
             reference_vectors=[dict(rs1=3,rs2=5,expected=8),dict(rs1=0xffffffff,rs2=1,expected=0)],
             mutants=[dict(id='wrong-xor',result=['xor','rs1','rs2'])])])


def write(tmp_path, data):
    path = tmp_path / 'custom.json'
    path.write_text(json.dumps(data))
    return path


def test_roundtrips_and_exports(tmp_path):
    path = write(tmp_path, spec())
    data = load(path)
    result = generate(path, tmp_path / 'generated')
    assert result['status'] == 'generated'
    assert result['gaps'] == []
    assert result['checks'][-1]['status'] == 'detected'
    decoder = runpy.run_path(str(tmp_path / 'generated/custom_disasm.py'))['decode']
    for rd in (0,1,31):
        for rs1 in (0,2,31):
            for rs2 in (0,3,31):
                word = encode(data['instructions'][0], rd, rs1, rs2)
                expected = dict(name='xadd', rd=rd, rs1=rs1, rs2=rs2)
                assert decode(data, word) == expected
                assert decoder(word) == expected
    assert decoder(0x33) is None
    plan = json.loads((tmp_path / 'generated/plan.json').read_text())
    assert any(v['origin']=='project-reference' and v['expected']==8 for v in plan['vectors'])
    assert 'rd aliases rs1' in plan['sequences'][0]['cases']


@pytest.mark.parametrize('change', [
    lambda d: d['instructions'].append(deepcopy(d['instructions'][0]) | {'name':'duplicate_encoding'}),
    lambda d: d['instructions'][0].update(match='0x33'),
    lambda d: d['instructions'][0].update(mask=127),
    lambda d: d['instructions'][0].update(result=['div','rs1','rs2']),
    lambda d: d['instructions'][0].update(state=['csr']),
    lambda d: d['instructions'][0].pop('result'),
])
def test_reject_unsupported_or_incomplete(tmp_path, change):
    data = spec()
    change(data)
    with pytest.raises((ValueError,KeyError)):
        load(write(tmp_path, data))


def test_independent_bad_reference_and_surviving_mutant(tmp_path):
    data = spec()
    data['instructions'][0]['reference_vectors'][0]['expected'] = 9
    result = generate(write(tmp_path, data), tmp_path / 'wrong')
    assert result['status'] == 'mismatch'
    data = spec()
    data['instructions'][0]['mutants'][0]['result'] = ['add','rs1','rs2']
    result = generate(write(tmp_path, data), tmp_path / 'survived')
    assert result['gaps'] == ['xadd: surviving mutant wrong-xor']


def test_bitvector_shift_and_wrap():
    assert expression(['add','rs1','rs2'],32,0xffffffff,2) == 1
    assert expression(['sll','rs1','rs2'],32,1,32) == 1
    assert expression(['srl','rs1','rs2'],64,1 << 63,63) == 1


@pytest.mark.parametrize('xlen', [32,64])
def test_native_gnu_hooks(tmp_path, xlen):
    gcc = shutil.which('riscv64-unknown-elf-gcc') or '/opt/homebrew/opt/riscv-gnu-toolchain/bin/riscv64-unknown-elf-gcc'
    if not Path(gcc).is_file():
        pytest.skip('RISC-V GNU compiler required')
    from rvw.common.proc import run_group
    out = tmp_path / 'generated'
    data = spec()
    data['xlen'] = xlen
    if xlen == 64:
        data['instructions'][0]['reference_vectors'][1]['expected'] = 0x100000000
    generate(write(tmp_path, data), out)
    c = out / 'hooks.c'
    c.write_text(f'#include "custom.h"\nuint{xlen}_t f(uint{xlen}_t a,uint{xlen}_t b) {{ return rvw_xadd(a,b); }}\n')
    for source in (c, out / 'tests.S'):
        with (out / (source.name + '.log')).open('w') as log:
            result = run_group([gcc,f'-march=rv{xlen}i','-mabi=' + ('ilp32' if xlen == 32 else 'lp64'),'-O2','-c',str(source),'-o',str(source.with_suffix('.o'))],
                               cwd=out, stdout=log, stderr=log, timeout=10)
        assert result.returncode == 0 and not result.timed_out
    objcopy = str(Path(gcc).with_name('riscv64-unknown-elf-objcopy'))
    subprocess.run([objcopy,'-O','binary','--only-section=.text',str(c.with_suffix('.o')),str(out / 'text.bin')],check=True,timeout=10)
    code = (out / 'text.bin').read_bytes()
    words = [int.from_bytes(code[i:i+4],'little') for i in range(0,len(code),4)]
    found = [decode(load(tmp_path / 'custom.json'),word) for word in words]
    assert any(d and d['name']=='xadd' and d['rd']==10 and d['rs1']==10 and d['rs2']==11 for d in found)
