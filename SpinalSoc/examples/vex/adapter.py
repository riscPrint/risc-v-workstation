#!/usr/bin/env python3
"""C1 smoke adapter for a composed VexRiscv SoC. Gate input capture is incomplete."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LIB = ROOT / 'SpinalSoc'


def image(elf, target):
    from rvw.cosim.elf import Elf
    obj = Elf(elf)
    if obj.xlen != 32 or obj.entry != 0x80000000:
        raise ValueError('ELF must be RV32 with entry 0x80000000')
    data = bytearray(65536)
    for address, payload, size in obj.segments:
        offset = address - 0x80000000
        if offset < 0 or offset + size > len(data):
            raise ValueError('ELF load segment must fit the 64 KiB RAM')
        data[offset:offset+len(payload)] = payload
    tohost = obj.symbols.get('tohost', 0)
    if tohost and (tohost % 4 or not 0x80000000 <= tohost < 0x80010000):
        raise ValueError('tohost must be an aligned RAM word')
    target.write_text(''.join(f'{int.from_bytes(data[i:i+4], "little"):08x}\n' for i in range(0,len(data),4)))
    return tohost


def revision(path):
    def git(*args):
        return subprocess.check_output(['git','-C',str(path),*args],text=True).strip()
    return git('rev-parse','HEAD'), bool(git('status','--porcelain'))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['identity','build','run','run-many'])
    p.add_argument('--manifest'); p.add_argument('--jobs', type=int, default=1)
    p.add_argument('--config', default='vex'); p.add_argument('--elf'); p.add_argument('--out')
    p.add_argument('--seed', type=int, default=31); p.add_argument('--max-cycles', type=int, default=100000)
    p.add_argument('--mem-latency', type=int, default=0); p.add_argument('--json', action='store_true')
    p.add_argument('--rvfi-trace', action='store_true'); p.add_argument('--wave', action='store_true')
    args = p.parse_args()
    core = Path(os.environ['VEXRISCV']).resolve()
    core_rev, core_dirty = revision(core)
    if args.action == 'identity':
        h = hashlib.sha256()
        for file in sorted([*core.glob('src/main/scala/**/*.scala'), *LIB.glob('src/**/*.scala'), *HERE.glob('*'), LIB/'build.sbt']):
            if file.is_file(): h.update(str(file.relative_to(core if file.is_relative_to(core) else ROOT)).encode()); h.update(file.read_bytes())
        print(h.hexdigest()); return 0
    from rvw.common.proc import run_group
    from rvw.soc.compose import compose
    external_cp = os.environ.get('RVW_SOC_CLASSPATH')
    if not external_cp:
        generated = LIB/'generated'
        if generated.exists(): shutil.rmtree(generated)
        compose(HERE/'compose.json', generated)
        build = run_group([str(ROOT/'scripts/with-lock.sh'),'sbt','nice','-n','10','sbt','-Drvw.soc.vex=true','compile','export Compile / dependencyClasspath'], cwd=LIB, timeout=300, capture=True)
        if build.returncode:
            print(build.stdout); print(build.stderr, file=sys.stderr); return 2
        cp = str(LIB/'target/scala-2.13/classes') + ':' + (LIB/'target/streams/compile/dependencyClasspath/_global/streams/export').read_text().strip()
    else:
        cp = external_cp
    if args.action == 'build': return 0
    jobs = [json.loads(row) for row in Path(args.manifest).read_text().splitlines() if row.strip()] if args.action == 'run-many' else [vars(args)]
    prepared = []
    for job in jobs:
        if job.get('config','vex') != 'vex' or job.get('mem_latency') not in (None,0) or job.get('rvfi_trace') or job.get('wave'):
            raise ValueError('only vex, fixed bus latency, no RVFI/waves are supported')
        if not job.get('elf') or not job.get('out') or job.get('max_cycles',100000) <= 0:
            raise ValueError('run needs ELF, output and a positive cycle limit')
        out = Path(job['out']).resolve(); out.mkdir(parents=True, exist_ok=True)
        captured = out/'program.elf'; captured.write_bytes(Path(job['elf']).read_bytes())
        words = out/'image.hex'; tohost = image(captured, words)
        prepared.append((job,out,words,tohost))
    if not prepared: raise ValueError('manifest has no jobs')
    manifest = prepared[0][1]/'native-jobs.tsv'
    manifest.write_text(''.join(f'{words}\t{job.get("seed",31)}\t{job.get("max_cycles",100000)}\t{tohost:x}\t{Path(job["elf"]).name}\n' for job,out,words,tohost in prepared))
    start = time.monotonic()
    native = run_group(['nice','-n','10','java','-Xmx3g','-cp',cp,'examplesocvex.Run',str(manifest)], cwd=LIB, timeout=120, capture=True)
    log = (native.stdout or '') + '\n' + (native.stderr or '')
    rows = [json.loads(line.split('SOC_RESULT ',1)[1]) for line in log.splitlines() if 'SOC_RESULT ' in line]
    tools_rev, tools_dirty = revision(ROOT)
    rtl = hashlib.sha256()
    for file in sorted((LIB/'simWorkspace/tmp/job_1').glob('*')):
        if file.is_file(): rtl.update(file.name.encode()); rtl.update(file.read_bytes())
    failed = False
    for index,(job,out,words,tohost) in enumerate(prepared):
        row = rows[index] if native.returncode == 0 and len(rows) == len(prepared) else dict(status='error',cycles=0,instret=0,fail_code=None,uart_hex='')
        uart = bytes.fromhex(row['uart_hex']).decode('utf-8',errors='replace')
        expected = {'hello':'hello\n','uart_irq':'I'}.get(Path(job['elf']).name)
        if row['status'] == 'pass' and expected is not None and uart != expected:
            row.update(status='fail',fail_code=None,message='UART output differs from expected bytes')
        (out/'run.log').write_text(log)
        report = dict(schema='rvw.run/1',core='soc-vex',config='vex',elf=str(Path(job['elf']).resolve()),
            elf_sha256=hashlib.sha256((out/'program.elf').read_bytes()).hexdigest(),rtl_sha256=rtl.hexdigest(),
            seed=job.get('seed',31),max_cycles=job.get('max_cycles',100000),mem_latency=0,
            status=row['status'],cycles=row['cycles'],instret=row['instret'],
            fail_code=row['fail_code'] if row['status']=='fail' else None,
            message='native run failed; see run.log' if row['status']=='error' else row.get('message'),wall_s=time.monotonic()-start,
            source=dict(core_repo=str(core),core_rev=core_rev[:12],core_rev_full=core_rev,core_dirty=core_dirty,
                        tools_repo=str(ROOT),tools_rev=tools_rev,tools_dirty=tools_dirty),
            tools=dict(spinalhdl='1.15.0',verilator=subprocess.check_output(['verilator','--version'],text=True).strip()),
            artifacts=dict(log='run.log'),replay=shlex.join([str(HERE/'run.sh'),'run','--elf',str(out/'program.elf'),'--out','REPLAY','--seed',str(job.get('seed',31)),'--max-cycles',str(job.get('max_cycles',100000))]),
            details=dict(profile='composed-vex-rv32im',uart=uart,external_classpath=bool(external_cp),gate_input_capture='incomplete'))
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report))
        failed |= row['status'] != 'pass'
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
