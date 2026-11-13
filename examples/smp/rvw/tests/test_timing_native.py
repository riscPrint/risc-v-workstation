"""Native replay and progress controls for real clock-enable/backpressure stalls."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import shlex
import shutil
import pytest
from rvw.common.proc import run_group
from rvw.results import load_run

pytestmark=pytest.mark.slow
ROOT=Path(__file__).resolve().parents[4]
PROJECT=ROOT/'examples/smp/rvw'


def test_native_clock_bus_stress_replay(tmp_path):
    if not os.environ.get('VEXIIRISCV') or not shutil.which('riscv64-unknown-elf-gcc'):
        pytest.skip('private VEXIIRISCV checkout and RISC-V GCC required')
    suite=runpy.run_path(str(PROJECT/'suite_programs.py'))['build']
    common=runpy.run_path(str(PROJECT/'cosim_program.py'))['build']
    summarize=runpy.run_path(str(PROJECT/'summarize.py'))['summarize']
    from rvw.memory.concurrent_build import build as random_build
    lrsc=tmp_path/'lrsc';suite(lrsc,'lrsc',17)
    amo=tmp_path/'amo';suite(amo,'amo',23)
    random=tmp_path/'random';built=random_build(random,seed=7,harts=2,length=4)
    assert built['status']=='built',built
    hsm=tmp_path/'hsm';common(hsm,source=(PROJECT/'programs/hsm.S').read_text())
    serial=tmp_path/'serial';common(serial,source=(PROJECT/'programs/serial-amo.S').read_text())
    cases=[('lrsc-a',lrsc,'hart-0.elf','smp2',17),('lrsc-b',lrsc,'hart-0.elf','smp2',17),
           ('amo',amo,'hart-0.elf','smp2',23),('random',random,'hart-0.elf','smp2',7),
           ('hsm',hsm,'shared.elf','hsm2',17),('serial',serial,'shared.elf','serial2',23)]
    jobs=[dict(elf=str(inputs/elf),hart_images=str(inputs/'hart-images.json'),
               out=str(tmp_path/(name+'-run')),config=config,seed=seed,max_cycles=200000,
               wall_timeout=90,rvfi_trace=True) for name,inputs,elf,config,seed in cases]
    manifest=tmp_path/'jobs.jsonl'
    manifest.write_text(''.join(json.dumps(j)+'\n' for j in jobs))
    settings=dict(RVW_SMP_MAX_DELAY='11',RVW_SMP_READY_PERCENT='60',RVW_SMP_CLOCK_PERCENT='70')
    env=dict(os.environ,RVW_HOME=str(ROOT),RVW_VEX_LOCK='vex-mem',
             RISCVSIM_WORK=str(tmp_path/'sim'),**settings)
    run=run_group(['nice','-n','10',str(PROJECT/'run.sh'),'run-many','--manifest',str(manifest),
                   '--jobs','1'],timeout=1200,capture=True,env=env)
    (tmp_path/'adapter.log').write_text(run.stdout+run.stderr)
    reports=[]
    for job in jobs:
        folder=Path(job['out']);loaded=load_run(folder/'result.json')
        assert loaded.status=='pass' and not loaded.why_inconclusive,(job,loaded,run.stdout[-4000:])
        c1=json.loads((folder/'result.json').read_text());timing=c1['details']['timing']
        assert timing['seed']==job['seed'] and timing['clock_enable_percent']==70
        assert timing['ready_percent']==60 and timing['random_max_delay']==11
        assert all(0 < n < timing['base_sample_edges'] for n in timing['clock_stall_edges'].values())
        words=shlex.split(c1['replay'])
        assert all(f'{k}={v}' in words for k,v in settings.items())
        report=summarize(folder);report['timing']=timing
        if job['config']=='hsm2':report['hsm']=c1['details']['hsm']
        reports.append(report)
    assert run.returncode==0 and not run.timed_out,run.stdout[-4000:]+run.stderr[-1000:]
    first=(tmp_path/'lrsc-a-run/rvfi.jsonl').read_bytes()
    replay=(tmp_path/'lrsc-b-run/rvfi.jsonl').read_bytes()
    assert first==replay,'same seed/settings/ELFs did not replay the exact C2 capture'
    (tmp_path/'stress-results.json').write_text(json.dumps(dict(runs=reports,
        replay=dict(status='identical',sha256=hashlib.sha256(first).hexdigest())),indent=2)+'\n')
