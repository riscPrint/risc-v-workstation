#!/usr/bin/env python3
"""Run captured ISA inputs with native binds, plus a bounded fabric check."""
import hashlib
import json
import os
from pathlib import Path
import sys

from rvw.common.proc import run_group
from rvw.soc.protocol_proof import prove

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
out, result, source = map(Path, sys.argv[1:])
classpath = (HERE/'../../out/vex-cp.txt').read_text().strip()
isa = ROOT/'examples/vexriscv/rvw/out/isa'
programs = sorted(p for p in isa.iterdir() if p.is_file() and __import__('re').fullmatch(r'rv32u[im]-p-.*',p.name) and 'ma_data' not in p.name)
if not programs:
    raise SystemExit('Missing input: built RV32UI/UM ISA ELFs in examples/vexriscv/rvw/out/isa')
jobs = out/'protocol-jobs.jsonl'
jobs.write_text(''.join(json.dumps(dict(config='vex',elf=str(p),out=str(out/'protocol-isa'/p.name),seed=31,max_cycles=100000))+'\n' for p in programs))
command = ['bash',str(HERE/'run.sh'),'run-many','--manifest',str(jobs)]
with (out/'protocol-isa.log').open('w') as log:
    native = run_group(command,cwd=ROOT,stdout=log,stderr=log,timeout=100)
path = out/'protocol-isa/suite.json'
# C3 uses summary.json. Require explicit per-case successes and real execution.
paths = list((out/'protocol-isa').glob('**/result.json'))
cases = [json.loads(p.read_text()) for p in paths]
passed = len(cases)==len(programs) and all(c.get('status')=='pass' and c.get('cycles',0)>0 for c in cases)
formal = prove(source,out/'protocol-formal',classpath,20)
status = 'pass' if native.returncode==0 and not native.timed_out and passed and formal['status']=='pass' else 'inconclusive'
if any(c.get('status')=='fail' for c in cases) or formal['status']=='fail':
    status='fail'
result.write_text(json.dumps(dict(schema='rvw.soc-verify-evidence/1',kind='protocol',
    map_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),status=status,
    checks=len(cases)+formal.get('checks',0),cases=len(cases),formal=formal,
    scope='Native protocol assertions over the captured ISA suite and an eight-cycle APB fabric check.')))
raise SystemExit(0 if status=='pass' else 1)
