"""Patch application and native generated software/reference hooks."""
import copy
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import pytest
from rvw.common.proc import run_group
from rvw.formal.custom_isa import generate

ROOT=Path(__file__).resolve().parents[2]
EXAMPLE=ROOT/'examples/custom-isa/xadd.json'


def source(tmp_path,xlen=32):
    data=json.loads(EXAMPLE.read_text());data['xlen']=xlen
    for row in data['instructions']:
        for vector in row.get('reference_vectors',[]):
            vector['expected']=(vector['rs1']+vector['rs2'])&((1<<xlen)-1)
    path=tmp_path/'custom.json';path.write_text(json.dumps(data));return path


def build_plugin(directory):
    prefix=Path(os.environ.get('SPIKE_PREFIX','/opt/homebrew'))
    if not (prefix/'include/riscv/extension.h').is_file() or not shutil.which('c++'):
        pytest.skip('native Spike headers/library and C++ compiler required')
    with (directory/'build.log').open('w') as log:
        result=run_group(['nice','-n','10','bash',str(directory/'build-spike.sh')],cwd=directory,stdout=log,stderr=log,timeout=60)
    assert result.returncode==0 and not result.timed_out,(directory/'build.log').read_text()
    return directory/'libcustom.so'


def test_default_fragments_do_not_claim_integrated_compiler(tmp_path):
    result=generate(source(tmp_path),tmp_path/'out')
    backend=result['backend_exports']
    assert backend['status']=='generated' and backend['compiler_bases'] is None and backend['gaps']
    for name in ('gcc.patch','llvm.patch','spike.cc','build-spike.sh','platform.fragment.json'):
        assert (tmp_path/'out/backends'/name).is_file()
    assert '__builtin' not in (tmp_path/'out/backends/gcc.patch').read_text()


@pytest.mark.parametrize('xlen',[32,64])
def test_pinned_compiler_patches_apply(tmp_path,xlen):
    root=os.environ.get('CUSTOM_BACKEND_BASES')
    if not root:pytest.skip('pinned GCC/LLVM source base files required')
    from rvw.cli import main
    assert main(['formal','custom-isa',str(source(tmp_path,xlen)),'--backend-sources',root,'--out',str(tmp_path/'out')])==0
    result=json.loads((tmp_path/'out/result.json').read_text())
    backend=result['backend_exports'];assert not backend['gaps']
    if xlen==32:
        for name in ('gcc.patch','llvm.patch'):
            assert (tmp_path/'out/backends'/name).read_bytes()==(ROOT/'examples/custom-isa/compiler-patches'/name).read_bytes()
        from rvw.formal.mcp_tools import _custom_isa
        class Job:
            def run(self,argv):return main(argv[3:])
        mcp=_custom_isa(Job(),manifest=str(tmp_path/'custom.json'),out=str(tmp_path/'mcp'),backend_sources=root)
        assert mcp['backend_exports']['compiler_bases'] is not None

    baseline=tmp_path/'base';baseline.mkdir()
    for record in backend['compiler_bases']['files']:
        target=baseline/record['path'];target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(Path(root)/record['path'],target)
    for patch in ('gcc.patch','llvm.patch'):
        path=tmp_path/'out/backends'/patch
        checked=run_group(['git','apply','--check',str(path)],cwd=baseline,capture=True,timeout=10)
        assert checked.returncode==0,checked.stderr
        applied=run_group(['git','apply',str(path)],cwd=baseline,capture=True,timeout=10)
        assert applied.returncode==0,applied.stderr
    md=(baseline/'gcc/config/riscv/riscv.md').read_text()
    builtins=(baseline/'gcc/config/riscv/riscv-builtins.cc').read_text()
    assert 'UNSPEC_RVW_XADD' in md and '(include "rvw-custom.md")' in md
    assert 'RISCV_BUILTIN_NO_PREFIX (rvw_xadd' in builtins
    assert 'include "RISCVInstrInfoRVWCustom.td"' in (baseline/'llvm/lib/Target/RISCV/RISCVInstrInfo.td').read_text()
    assert 'int_riscv_rvw_xadd' in (baseline/'llvm/include/llvm/IR/IntrinsicsRVWCustom.td').read_text()
    # Hash drift must fail before a patch can claim these bases.
    md_path=Path(root)/'gcc/config/riscv/riscv.md'
    copied=tmp_path/'drift';shutil.copytree(root,copied)
    (copied/'gcc/config/riscv/riscv.md').write_bytes(md_path.read_bytes()+b'changed\n')
    with pytest.raises(ValueError,match='hash differs'):
        generate(source(tmp_path),tmp_path/'bad',copied)


@pytest.mark.parametrize('xlen',[32,64])
def test_native_generated_cpp_word_semantics(tmp_path,xlen):
    mask=(1<<xlen)-1;sign=1<<(xlen-1)
    cases={'add':[(3,5,8),(mask,1,0)],'sub':[(3,5,mask-1),(0,1,mask)],
           'xor':[(3,5,6),(mask,mask,0)],'and':[(3,5,1),(mask,0,0)],
           'or':[(3,5,7),(0,mask,mask)],'sll':[(1,xlen,1),(sign,1,0),(1,xlen-1,sign)],
           'srl':[(sign,xlen-1,1),(sign,xlen,sign)]}
    data=json.loads(source(tmp_path,xlen).read_text());template=data['instructions'][0];data['instructions']=[]
    for i,(op,vectors) in enumerate(cases.items()):
        row=copy.deepcopy(template);row.update(name='x'+op,match=0x0b|(i<<12),result=[op,'rs1','rs2'],mutants=[],
              reference_vectors=[dict(rs1=a,rs2=b,expected=value) for a,b,value in vectors])
        data['instructions'].append(row)
    path=tmp_path/'all-ops.json';path.write_text(json.dumps(data))
    generated=generate(path,tmp_path/'out')
    directory=tmp_path/'out/backends';library=build_plugin(directory)
    import sys
    script="""import ctypes,json,sys
plugin=ctypes.CDLL(sys.argv[1],mode=ctypes.RTLD_GLOBAL)
evaluate=plugin.rvw_custom_eval
evaluate.argtypes=[ctypes.c_uint,ctypes.c_uint64,ctypes.c_uint64]
evaluate.restype=ctypes.c_uint64
for index,vectors in enumerate(json.loads(sys.argv[2])):
    for a,b,expected in vectors:
        assert evaluate(index,a,b)==expected
"""
    checked=run_group([sys.executable,'-c',script,str(library),json.dumps(list(cases.values()))],capture=True,timeout=20)
    assert checked.returncode==0,checked.stderr
    config=json.loads((directory/'platform.fragment.json').read_text())
    assert config['reference_extensions'][0]['name']==generated['backend_exports']['extension_name']


@pytest.mark.parametrize('xlen',[32,64])
def test_native_compiled_calling_convention_and_spike_registration(tmp_path,xlen):
    from rvw.cosim.platform import Platform
    from rvw.cosim.spike import Spike,capture_shim
    from rvw.common.capture import Capture
    from rvw.cosim.custom import capture_extensions
    gcc=shutil.which('riscv64-unknown-elf-gcc') or '/opt/homebrew/opt/riscv-gnu-toolchain/bin/riscv64-unknown-elf-gcc'
    shim=Path(os.environ.get('RVW_SPIKE_SHIM',ROOT/'Cosim/build/librvw_spike.so'))
    if not Path(gcc).is_file() or not shim.is_file():pytest.skip('native RISC-V GCC and co-simulation shim required')
    result=generate(source(tmp_path,xlen),tmp_path/'out');directory=tmp_path/'out/backends';library=build_plugin(directory)
    c=tmp_path/'smoke.c';c.write_text(f'#include "custom.h"\n__attribute__((noinline)) uint{xlen}_t smoke(uint{xlen}_t a,uint{xlen}_t b) {{ return rvw_xadd(a,b); }}\n')
    start=tmp_path/'start.S';start.write_text('''.section .text.start
.globl _start
_start:
 li sp,0x80010000
 li a0,7
 li a1,3
 call smoke
 li t0,10
 bne a0,t0,failed
 j done
failed:
 li a0,0xdead
.globl done
done:
 j done
''')
    linker=tmp_path/'program.ld';linker.write_text('ENTRY(_start)\nSECTIONS { . = 0x80000000; .text : { *(.text.start) *(.text*) } .data : { *(.data*) } .bss : { *(.bss*) } }\n')
    elf=tmp_path/'smoke.elf'
    compiled=run_group(['nice','-n','10',gcc,f'-march=rv{xlen}i','-mabi='+('ilp32' if xlen==32 else 'lp64'),'-O2','-ffreestanding','-nostdlib','-nostartfiles','-fno-stack-protector',
        '-Wl,--no-relax','-Wl,--build-id=none','-Wl,-T,'+str(linker),'-I'+str(tmp_path/'out'),str(start),str(c),'-o',str(elf)],capture=True,timeout=30)
    assert compiled.returncode==0,compiled.stderr
    symbols=run_group([str(Path(gcc).with_name('riscv64-unknown-elf-nm')),str(elf)],capture=True,timeout=10)
    done=int(next(line.split()[0] for line in symbols.stdout.splitlines() if line.split()[-1]=='done'),16)
    platform=Platform('custom-software',xlen,f'rv{xlen}i',0x80000000,[(0x80000000,0x10000)],[],pmp_regions=0)
    capture=Capture(tmp_path/'captured-inputs')
    image=capture.file(elf).copy
    captured_shim=capture_shim(capture,shim)
    platform.reference_extensions=capture_extensions([dict(name=result['backend_exports']['extension_name'],library=str(library))],capture,directory/'platform.fragment.json')
    model=Spike(platform,image,shim=captured_shim)
    observed=[]
    try:
        for _ in range(64):
            effect=model.step();assert not effect['trap'],effect
            if effect['insn']&0xfe00707f==0x0b:observed.append(effect)
            if effect['pc_next']==done:break
        else:pytest.fail('compiled program did not finish')
        assert model.regs[10]==10
        assert len(observed)==1 and observed[0]['rd']==10 and observed[0]['rd_wdata']==10
        assert 'xadd' in observed[0]['disasm']
    finally:model.close()
    platform.reference_extensions=[]
    model=Spike(platform,image,shim=captured_shim)
    try:
        for _ in range(64):
            effect=model.step()
            if effect['trap']:
                assert effect['cause']==2
                break
        else:pytest.fail('unregistered custom instruction did not trap')
    finally:model.close()
