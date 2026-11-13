"""Real VexRiscv execution with optional generated CSR and HPM monitors."""
import json
import os
from pathlib import Path
import shutil
import pytest
from rvw.common.proc import run_group
from rvw.formal.csr import generate

pytestmark=pytest.mark.slow


@pytest.fixture(scope='module')
def programs(tmp_path_factory):
    root=Path(__file__).resolve().parents[3]
    source=os.environ.get('VEXRISCV')
    if not source or not (Path(source)/'src/main/scala/vexriscv/plugin/CsrPlugin.scala').is_file():
        pytest.skip('VEXRISCV must select an external checkout; use a private copy for parallel runs')
    gcc=shutil.which('riscv64-unknown-elf-gcc')
    if not gcc:
        candidate=Path('/opt/homebrew/opt/riscv-gnu-toolchain/bin/riscv64-unknown-elf-gcc')
        if candidate.is_file():gcc=str(candidate)
    if not gcc or any(not shutil.which(t) for t in ('spike','sbt','verilator')):
        pytest.skip('RISC-V GCC, Spike, sbt and Verilator required')
    out=tmp_path_factory.mktemp('vex-csr-checks')
    generate(root/'examples/vexriscv/csr.json',out/'generated')
    elfs=[]
    for name,src in [('mscratch',out/'generated/mscratch.S'),('sscratch',out/'generated/sscratch.S'),
                     ('events',root/'examples/vexriscv/rvw/programs/csr-check-events.S')]:
        elf=out/(name+'.elf')
        r=run_group([gcc,'-march=rv32im_zicsr','-mabi=ilp32','-nostdlib','-nostartfiles',
                     '-T',str(root/'examples/vexriscv/rvw/programs/link.ld'),str(src),'-o',str(elf)],capture=True,timeout=20)
        assert r.returncode==0,r.stdout+r.stderr
        isa='rv32im_zicsr_zifencei_zicntr' if name=='events' else 'rv32im_zicsr_zifencei'
        r=run_group(['nice','-n','10','spike','--isa='+isa,'--priv=m',str(elf)],capture=True,timeout=20)
        assert r.returncode==0,name+": "+r.stdout+r.stderr
        elfs.append(elf)
    return root,out/'generated/model.json',elfs


@pytest.mark.parametrize('fault',['none','csr','hpm','hpm_read'])
def test_vex_native_checks(tmp_path,programs,fault):
    root,model,elfs=programs
    out=tmp_path/'run'
    args=' '.join(json.dumps(str(p)) for p in (model,out))+ ' '+fault+' '+ ' '.join(json.dumps(str(p)) for p in elfs)
    env=dict(os.environ,RVW_HOME=str(root))
    r=run_group([str(root/'scripts/with-lock.sh'),os.environ.get('RVW_VEX_CHECKS_LOCK','vex-generated-checks'),
                 str(root/'scripts/with-lock.sh'),os.environ.get('RVW_SBT_LOCK','sbt'),'nice','-n','10','sbt','-batch',
                 'runMain rvwvex.CsrChecksRuntime '+args],cwd=root/'examples/vexriscv/rvw',env=env,capture=True,timeout=110)
    (tmp_path/'native.log').write_text(r.stdout+r.stderr)
    assert r.returncode==0 and not r.timed_out,r.stdout+r.stderr
    assert 'CSR_CHECKS_RUNTIME_OK fault='+fault in r.stdout
    reports=[json.loads((out/f'run_{i}.json').read_text()) for i in range(3)]
    for report in reports:
        assert report['inserted']==9 and report['retired']>0
        assert report['observation_fault']==fault
    if fault=='none':
        assert all(p['status']=='pass' and p['fired']==0 for p in reports)
    if fault=='csr':
        assert reports[0]['status']=='fail'
        assert any(f['kind']=='csr.state' for f in reports[0]['firings'])
    if fault=='hpm':
        assert all(p['status']=='fail' and any(f['kind']=='hpm.count' for f in p['firings']) for p in reports)

    if fault=='hpm_read':
        assert reports[2]['status']=='fail'
        assert {f['id'] for f in reports[2]['firings']}=={
            'hpm.read:mcycle_machine','hpm.read:minstret_machine','hpm.read:mcycle_user','hpm.read:minstret_user'}


def test_vex_isa_all_generated_checks_record_findings(tmp_path, programs):
    root,model,_=programs
    elfs=sorted(f for f in (root/'examples/vexriscv/rvw/out/isa').glob('rv32u[im]-p-*')
                if f.is_file() and f.suffix!='.dump' and f.name!='rv32ui-p-ma_data')
    if not elfs: pytest.skip('build aligned ISA ELFs with examples/vexriscv/rvw/build-tests.sh')
    out=tmp_path/'isa'
    args=' '.join(json.dumps(str(p)) for p in (model,out,'none',*elfs))
    r=run_group([str(root/'scripts/with-lock.sh'),os.environ.get('RVW_VEX_CHECKS_LOCK','vex-csr'),str(root/'scripts/with-lock.sh'),
        os.environ.get('RVW_SBT_LOCK','sbt'),'nice','-n','10','sbt','-batch','runMain rvwvex.CsrChecksRuntime '+args],
        cwd=root/'examples/vexriscv/rvw',env=dict(os.environ,RVW_HOME=str(root),RVW_CHECKS_ISA='1'),
        capture=True,timeout=240)
    (tmp_path/'native.log').write_text(r.stdout+r.stderr)
    assert r.returncode==1 and not r.timed_out,r.stdout+r.stderr
    from rvw.checks.qualification import summarize
    runs=sorted(out.glob('c1_*.json'))
    assert len(runs)==len(elfs)
    report=summarize(out/'checks.json',runs)
    assert report['status']=='findings'
    assert {k for k,v in report['counts'].items() if v['fired']}=={'stream.valid_hold'}
    for path in runs:
        run=json.loads(path.read_text())
        assert run['status']=='fail' and run['details']['assertions_compiled'] is True
        assert run['instret']>0
