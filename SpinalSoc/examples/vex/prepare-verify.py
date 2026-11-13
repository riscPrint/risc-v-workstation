#!/usr/bin/env python3
"""Prepare fresh single-clock and multi-domain databases, then run the CPU."""
from pathlib import Path
import sys

from rvw.common.proc import run_group

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
out = Path(sys.argv[1]).resolve()
cpfile = HERE/'../../out/database-cp.txt'
classpath = cpfile.read_text().strip()
# Classpaths must be rebuilt from the current sources before using this helper.
for name, spec, cls in [('single', 'compose.json', 'generated.ComposedSoc'),
                        ('multi', 'compose-multidomain.json', 'generated.MultiDomainSoc')]:
    if name != sys.argv[2]:
        continue
    directory = out/name
    directory.mkdir()
    command = ['nice','-n','10','java','-Xss64m','-Xmx3g','-cp',classpath,
               'rvwsoc.Database',str(directory/'soc.db'),'50000000','async_high',cls,
               '--rtl',str(directory/'rtl'),'--no-blocks','--no-hgldd']
    with (directory/'extract.log').open('w') as log:
        process = run_group(command,cwd=ROOT,stdout=log,stderr=log,timeout=45)
    if process.returncode or process.timed_out:
        raise SystemExit('Database extraction failed: '+name)
