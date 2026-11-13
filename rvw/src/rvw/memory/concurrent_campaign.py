"""Bounded generated-program execution through an explicit project C1 adapter."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

from rvw.common.proc import run_group
from rvw.cosim.trace import Trace
from rvw.results import load_run
from rvw.runs.elf import Elf
from .concurrent_build import build


def identities(rows):
    pairs=[(row['hart'], row['elf_sha256']) for row in rows]
    if len({h for h,_ in pairs}) != len(pairs):
        raise ValueError('duplicate captured image hart')
    return dict(pairs)


def capture(trace, manifest, programs, elfs):
    expected=identities(manifest['harts'])
    metadata={row['hart']: row for row in programs}
    first, last, counts = {}, {}, {}
    reader=Trace(trace)
    try:
        if not reader.multihart or set(reader.header['harts']) != set(expected):
            raise ValueError('trace hart set differs from generated images')
        if identities(reader.header.get('hart_images', [])) != expected:
            raise ValueError('trace image hashes differ from generated images')
        for record in reader:
            if record.get('event'):
                continue
            h=record['hart']; pc=record['pc']; elf=elfs[h]
            entry=int(metadata[h]['entry'],0); end=int(metadata[h]['completion_pc'],0)
            if not entry <= pc <= end or (pc-entry)%4:
                raise ValueError('retired PC is outside its generated program')
            offset=elf.file_offset(pc)
            if offset is None or int.from_bytes(elf.data[offset:offset+4],'little') != record['insn']:
                raise ValueError('retired instruction differs from captured ELF bytes')
            first.setdefault(h,pc); last[h]=record; counts[h]=counts.get(h,0)+1
            if sum(counts.values()) > 10000:
                raise ValueError('concurrent smoke exceeds 10000 captured retirements')
        for h in expected:
            if first.get(h) != int(metadata[h]['entry'],0):
                raise ValueError('hart did not start at its generated entry')
            end=int(metadata[h]['completion_pc'],0)
            if last[h]['pc'] != end and last[h]['pc_next'] != end:
                raise ValueError('hart trace did not reach its generated completion PC')
        return {'retirements': sum(counts.values()), 'per_hart': counts,
                'trace_sha256': hashlib.sha256(Path(trace).read_bytes()).hexdigest()}
    finally:
        reader.close()


def run(out, adapter, config, seed=1, harts=2, length=16, model='rvwmo',
        gcc='riscv64-unknown-elf-gcc', max_cycles=20000, timeout=60, limit=100000,
        base=0x80000000, shared_base=0x81000000):
    if model not in ('rvwmo','ztso') or not config or not 0 < timeout <= 90 or max_cycles < 1 or limit < 1:
        raise ValueError('model, config and positive bounded campaign limits required; timeout at most 90 seconds')
    report={'schema':'rvw.concurrent-campaign/1','status':'inconclusive','model':model,
            'seed':seed,'harts':harts,'length':length,'adapter_invoked':False,
            'scope':'generated program capture and finite scalar ordering only'}
    executable=shutil.which(str(adapter))
    if executable is None:
        return report | {'reason':'project adapter executable is unavailable'}
    root=Path(out).resolve(); root.mkdir(parents=True,exist_ok=False)
    def finish(result):
        (root/'campaign.json').write_text(json.dumps(result,indent=2)+'\n')
        return result
    deadline=time.monotonic()+timeout
    def remaining():
        value=deadline-time.monotonic()
        if value <= 0:
            raise ValueError('total concurrent campaign timeout')
        return value
    stage='build'
    try:
        built=build(root/'inputs',seed,harts,length,gcc,base=base,shared_base=shared_base,timeout=min(30,remaining()))
        report['build']=built
        if built['status'] != 'built':
            return finish(report | {'stage':stage,'reason':built.get('reason','programs were not built')})
        manifest=json.loads(Path(built['hart_images']).read_text())
        expected=identities(manifest['harts'])
        # Keep pre-launch bytes. Adapters can compile or replace files after capture.
        elfs={row['hart']: Elf(row['elf']) for row in manifest['harts']}
        if any(hashlib.sha256(elf.data).hexdigest()!=expected[h] for h,elf in elfs.items()):
            raise ValueError('generated ELF changed before adapter launch')
        primary=manifest['harts'][0]
        runtime=remaining()
        command=['nice','-n','10',executable,'run','--config',config,'--elf',primary['elf'],
                 '--hart-images',built['hart_images'],'--out',str(root/'run'),'--seed',str(seed),
                 '--max-cycles',str(max_cycles),'--wall-timeout',str(runtime),'--rvfi-trace','--json']
        stage='adapter'; report['adapter_invoked']=True
        report['adapter']={'command':command,'sha256':hashlib.sha256(Path(executable).read_bytes()).hexdigest()}
        native=run_group(command,timeout=runtime,capture=True)
        (root/'adapter.log').write_text(native.stdout+native.stderr)
        report['adapter'].update(exit=native.returncode,timed_out=native.timed_out)
        if native.timed_out:
            return finish(report | {'stage':stage,'reason':'project adapter timeout'})
        result=load_run(root/'run')
        report['c1_status']=result.status
        if result.why_inconclusive:
            return finish(report | {'stage':stage,'reason':result.why_inconclusive})
        if result.status != 'pass':
            status='fail' if result.status in ('fail','assert','rvfi_error') else 'inconclusive'
            return finish(report | {'status':status,'stage':stage,'reason':'project adapter did not complete with pass'})
        if native.returncode:
            return finish(report | {'stage':stage,'reason':'nonzero adapter exit despite passing C1'})
        stage='capture'
        if result.config != config or result.seed != seed or result.max_cycles != max_cycles or result.elf_sha256 != primary['elf_sha256']:
            raise ValueError('C1 config, seed, cycle limit or primary ELF identity differs from requested run')
        if identities(result.details.get('hart_images',[])) != expected:
            raise ValueError('C1 image hashes differ from generated images')
        trace=result.artifact('rvfi_trace')
        if trace is None:
            raise ValueError('project adapter did not produce C2')
        report['capture']=capture(trace,manifest,built['programs'],elfs)
        stage='axiomatic'
        command=['nice','-n','10',sys.executable,'-m','rvw','memory','axiomatic',
                 '--trace',str(trace),'--reference',built['reference'],'--model',model,'--limit',str(limit)]
        checked=run_group(command,timeout=remaining(),capture=True)
        (root/'axiomatic.log').write_text(checked.stdout+checked.stderr)
        if checked.timed_out:
            return finish(report | {'stage':stage,'reason':'axiomatic candidate search timeout'})
        answer=json.loads(checked.stdout)
        expected_exit={'allowed':0,'forbidden':1,'inconclusive':3}
        if answer.get('status') not in expected_exit or checked.returncode != expected_exit[answer['status']]:
            raise ValueError('axiomatic checker result or exit code is invalid')
        if answer['status'] in ('allowed','forbidden') and (answer.get('schema') != 'rvw.axiomatic/1' or answer.get('model') != model):
            raise ValueError('axiomatic checker returned a different model or schema')
        return finish(report | {'status':answer['status'],'stage':stage,'axiomatic':answer})
    except (OSError,ValueError,KeyError,TypeError) as exc:
        return finish(report | {'stage':stage,'reason':str(exc)})
