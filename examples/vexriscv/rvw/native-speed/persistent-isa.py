#!/usr/bin/env python3
"""Compare one persistent JVM with 49 separate JVMs on identical ISA ELFs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from rvw.common.proc import run_group

p = argparse.ArgumentParser(__doc__)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--classpath-prefix', type=Path)
a = p.parse_args()
repo = Path(os.environ['RVW_HOME']).resolve()
example = Path(__file__).resolve().parents[1]
a.out = a.out.resolve()
a.out.mkdir(parents=True, exist_ok=False)
classfile = example / 'target/streams/runtime/fullClasspath/_global/streams/export'
classpath = classfile.read_text().strip()
if a.classpath_prefix:
    classpath = str(a.classpath_prefix.resolve()) + ':' + classpath
elfs = sorted(p for p in (example/'out/isa').glob('rv32u*-p-*') if p.name != 'rv32ui-p-ma_data')
if len(elfs) != 49:
    raise SystemExit(f'expected 49 aligned RV32UI/UM ELFs, found {len(elfs)}')

def checked(command, **kwargs):
    result = run_group(command, capture=True, text=True, timeout=600, **kwargs)
    if result.returncode or result.timed_out:
        raise RuntimeError(result.stdout[-2000:] + result.stderr[-2000:])
    return result

source = checked([sys.executable, str(repo/'RiscvSim/scripts/source-identity.py'), os.environ['VEXRISCV'], str(repo)])
(a.out/'source.json').write_text(source.stdout)
env = dict(os.environ, SPINAL_MAKE_CMD=str(repo/'RiscvSim/scripts/make-jobs.sh'))
native = checked([sys.executable, str(repo/'RiscvSim/scripts/native-identity.py')], env=env)
command = [sys.executable, str(repo/'RiscvSim/scripts/native-identity.py'), 'launch', native.stdout,
           str(a.out), '-Xmx3g', '-Xss64m', '-Driscvsim.tools='+str(repo),
           '-Driscvsim.source='+str(a.out/'source.json'),
           '-Driscvsim.script='+str(example/'run.sh'), '-cp', classpath, 'rvwvex.Main']

def job(elf, name):
    return dict(elf=str(elf), out=str(a.out/name/elf.name), seed=317,
                max_cycles=200000, mem_latency=0, rvfi_trace=True)
# Warm the generated native model cache outside both measured intervals.
warm = job(elfs[0], 'warm')
checked(command + ['run', '--elf', warm['elf'], '--out', warm['out'], '--seed', '317',
                   '--mem-latency', '0', '--max-cycles', '200000', '--rvfi-trace', '--json'], env=env)
started = time.monotonic()
server = checked(command + ['serve'], input=''.join(json.dumps(job(elf, 'server'))+'\n' for elf in elfs), env=env)
server_s = time.monotonic() - started
replies = [json.loads(line)['result'] for line in server.stdout.splitlines()]
if len(replies) != 49 or any(r['status'] != 'pass' or r.get('inconclusive') for r in replies):
    raise RuntimeError('persistent suite did not produce 49 conclusive passes')
started = time.monotonic()
rows = []
for elf in elfs:
    j = job(elf, 'process')
    fresh = checked(command + ['run', '--elf', j['elf'], '--out', j['out'], '--seed', '317',
                    '--mem-latency', '0', '--max-cycles', '200000', '--rvfi-trace', '--json'], env=env)
    report = json.loads(fresh.stdout)
    left = (a.out/'server'/elf.name/'rvfi.jsonl').read_bytes()
    right = (Path(j['out'])/'rvfi.jsonl').read_bytes()
    if report['status'] != 'pass' or report.get('inconclusive') or left != right:
        raise RuntimeError('fresh-process status or C2 differs: '+elf.name)
    rows.append(dict(test=elf.name, cycles=report['cycles'], instructions=report['instret'],
                     elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),
                     c2_sha256=hashlib.sha256(left).hexdigest()))
process_s = time.monotonic()-started
summary = dict(schema='rvw.persistent-isa-speed/1', rows=rows, tests=49,
               persistent_s=server_s, process_s=process_s, speedup=process_s/server_s,
               persistent_tests_per_s=49/server_s, process_tests_per_s=49/process_s,
               scope='one warmed suite; includes JVM launch, elaboration, run and C2 capture; excludes Scala compilation and shared tool/source capture')
(a.out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
print(json.dumps(summary))
