"""Pinned workload builds, Spike checks, C2 captures and shared sampled timing."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
from rvw.common.proc import run_group
from rvw.ooo.project import configuration
from rvw.ooo.sampled import sampled
from rvw.ooo.windows import digest as trace_digest
from rvw.csim.cli import simpoint_json
from .core import ASSETS, build, verify, recipe, digest

ROOT = Path(__file__).resolve().parents[4]


def evaluate(out, sources=None, builds=None, manifest=None, timeout=600, traces=None):
    sources, builds, traces = sources or {}, builds or {}, traces or {}
    mp = Path(manifest).resolve() if manifest else ASSETS/'evaluation.json'
    spec = json.loads(mp.read_text())
    if spec.get('schema') != 'rvw.workload-evaluation/1':
        raise ValueError('expected rvw.workload-evaluation/1')
    dest = Path(out).resolve()
    dest.mkdir(parents=True,exist_ok=False)
    models = {}
    for name,path in spec['models'].items():
        source = (ROOT/path).resolve() if not manifest else (mp.parent/path).resolve()
        config = configuration(json.loads(source.read_text()))
        target = dest/(name+'.json')
        target.write_text(json.dumps(asdict(config),indent=2)+'\n')
        models[name] = (target,digest(source))
    rows = []
    for group in spec['groups']:
        name = group['recipe']
        if name in builds:
            bp = Path(builds[name]).resolve()
            built = json.loads(bp.read_text())
            if not manifest and built.get('manifest') != json.loads(recipe(name).read_text()):
                raise ValueError('prebuilt workload manifest differs from the pinned recipe')
            ids = {w['id'] for w in built['workloads']}
            if ids != set(group['bench'].split(',')):
                raise ValueError('prebuilt workload selection differs from evaluation group')
        else:
            built = build(recipe(name),sources[name],dest/(name+'-build'),
                          'riscv64-unknown-elf-gcc',group['bench'])
            bp = dest/(name+'-build')/'build.json'
        checked = verify(bp,dest/(name+'-check'),'spike',timeout,False)
        if checked['status'] != 'pass':
            raise ValueError('workload output check failed: '+name)
        for w in built['workloads']:
            wd = dest/w['id']; wd.mkdir()
            trace = Path(traces[w['id']]).resolve() if w['id'] in traces else wd/'trace.jsonl'
            command = [sys.executable,'-m','rvw','cosim','generate','--elf',w['elf'],
                       '--core','workloads','--platform',str(ASSETS/'evaluation-platform.json'),
                       '--out',str(trace),'--max-instructions',str(spec['max_instructions']),'--json']
            if w['id'] not in traces:
                result = run_group(['nice','-n','10',*command],timeout=timeout,capture=True,
                                   env={**os.environ, 'RVW_SPIKE_MEMORY_LOG':'1'})
                (wd/'generation.json').write_text(result.stdout or '')
                (wd/'generation.stderr').write_text(result.stderr or '')
                if result.timed_out or result.returncode:
                    raise ValueError('Spike C2 generation failed: '+w['id'])
            with trace.open() as stream:
                header=json.loads(stream.readline())
            if Path(header['elf']).resolve()!=Path(w['elf']).resolve():
                raise ValueError('C2 ELF path differs from the verified workload')
            if header.get('elf_sha256',w['elf_sha256'])!=w['elf_sha256']:
                raise ValueError('C2 ELF hash differs from the verified workload')
            source_hash=trace_digest(trace)
            points = simpoint_json(trace,spec['interval'],spec['max_k'],15,spec['seed'],'c2')
            points['source_c2_sha256']=source_hash
            pp = wd/'points.json'; pp.write_text(json.dumps(points,indent=2)+'\n')
            timings = {}
            for model,(config,model_source_hash) in models.items():
                r = sampled(config,trace,pp,wd/(model+'.json'),spec['warmup'],10000000)
                timings[model] = dict(ipc=r['sampled_ipc'],estimated_cycles=r['estimated_cycles'],
                                      model_source_sha256=model_source_hash,config_sha256=r['config_sha256'])
            rows.append(dict(id=w['id'],elf_sha256=w['elf_sha256'],trace_sha256=source_hash,
                             trace_elf_binding='hash' if header.get('elf_sha256') else 'producer_path',
                             instructions=points['instructions'],points=len(points['points']),models=timings))
    report = dict(schema='rvw.workload-evaluation-report/1',status='reported',evidence='approximate-model',
                  accuracy_status='inconclusive',manifest_sha256=digest(mp),workloads=rows,
                  spike_diagnostic_log='memory',
                  limits=spec['limits']+['bounded warmup; sampling error is not measured against full timing',
                                        'Spike checks program outputs; it does not establish RTL timing accuracy',
                                        'own-model projection uses shared CPU dimensions and ooo settings; gem5-only cache and predictor tables are not used'])
    (dest/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    text=['# Approximate workload evaluation','','| Workload | Instructions | Points | '+' | '.join(models)+' |',
          '|---|---:|---:|'+'---:|'*len(models)]
    text += ['| '+w['id']+' | '+str(w['instructions'])+' | '+str(w['points'])+' | '+
             ' | '.join(f'{w["models"][m]["ipc"]:.4f}' for m in models)+' |' for w in rows]
    text += ['','Values are sampled model IPC. They are not measured commercial CPU performance.']
    (dest/'report.md').write_text('\n'.join(text)+'\n')
    return report
