"""Native VexiiRiscv CSR read binding, generated instructions and Spike controls."""
import json
import os
from pathlib import Path
import shutil
import pytest
from rvw.common.proc import run_group
from rvw.formal.csr import generate

pytestmark = pytest.mark.slow


@pytest.fixture(scope='module')
def programs(tmp_path_factory):
    root=Path(__file__).resolve().parents[3]
    source=os.environ.get('VEXIIRISCV')
    if not source or not (Path(source)/'src/main/scala/vexiiriscv/execute/CsrAccessPlugin.scala').is_file():
        pytest.skip('VEXIIRISCV must select a private pinned core with its SpinalHDL dependencies')
    if any(not shutil.which(t) for t in ('sbt','verilator','spike')):
        pytest.skip('native Scala, Verilator and Spike required')
    gcc=shutil.which('riscv64-unknown-elf-gcc') or '/opt/homebrew/opt/riscv-gnu-toolchain/bin/riscv64-unknown-elf-gcc'
    if not Path(gcc).is_file(): pytest.skip('RISC-V GCC required')
    out=tmp_path_factory.mktemp('vexii-csr')
    generate(root/'examples/vexiiriscv/csr.json',out/'generated')
    elfs=[]
    for name in ('mscratch','sscratch'):
        elf=out/(name+'.elf');elfs.append(elf)
        r=run_group([gcc,'-march=rv32im_zicsr','-mabi=ilp32','-nostdlib','-nostartfiles','-T',
            str(root/'examples/vexriscv/rvw/programs/link.ld'),str(out/'generated'/(name+'.S')),'-o',str(elf)],
            capture=True,timeout=20)
        assert r.returncode==0,r.stdout+r.stderr
        r=run_group(['nice','-n','10','spike','--isa=rv32im_zicsr_zifencei','--priv=m',str(elf)],capture=True,timeout=20)
        assert r.returncode==0,r.stdout+r.stderr
    return root,out/'generated/model.json',elfs


@pytest.mark.parametrize('fault',['none','read'])
def test_native_vexii_csr_read_binding(tmp_path,programs,fault):
    root,model,elfs=programs
    out=tmp_path/'native'
    args=' '.join(json.dumps(str(p)) for p in (model,out,fault,*elfs))
    r=run_group([str(root/'scripts/with-lock.sh'),os.environ.get('RVW_VEX_CHECKS_LOCK','vex-csr'),str(root/'scripts/with-lock.sh'),os.environ.get('RVW_SBT_LOCK','sbt'),
        'nice','-n','10','sbt','-batch','++2.13.14!','runMain rvwvexii.CsrChecksRuntime '+args],
        cwd=root/'examples/vexiiriscv/rvw',env=dict(os.environ,RVW_HOME=str(root)),capture=True,timeout=240)
    (tmp_path/'native.log').write_text(r.stdout+r.stderr)
    assert r.returncode==0 and not r.timed_out,r.stdout+r.stderr
    reports=[json.loads((out/f'run_{i}.json').read_text()) for i in range(2)]
    assert all(p['inserted']==1 and p['retired']>0 for p in reports)
    if fault=='none': assert all(p['status']=='pass' and p['fired']==0 for p in reports)
    else:
        assert reports[0]['status']=='fail' and reports[0]['fired']==1
        assert reports[0]['firings'][0]['kind']=='csr.read'
        assert reports[1]['status']=='pass' and reports[1]['fired']==0
