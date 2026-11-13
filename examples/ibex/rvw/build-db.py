"""Use the simulation source list for the whole-core slang import."""
import json, os, subprocess, sys
from pathlib import Path
spec=json.loads((Path(os.environ['IBEX_WORK'])/'hdl.json').read_text())
args=['rvw','query','build-hdl','--frontend','slang','--top',spec['top'],'--out',sys.argv[2], '--param','RV32M=ibex_pkg::RV32MSlow']
for inc in spec['include_dirs']: args+=['-I',inc]
for define in spec['defines']:
    if define != 'RVFI': args+=['--define',define]
subprocess.run([*args,*spec['sources']],check=True)
