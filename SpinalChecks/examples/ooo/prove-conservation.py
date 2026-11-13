#!/usr/bin/env python3
"""Prepare conservation with asserted ownership helpers, then run a short proof."""
import argparse
import importlib.util
from pathlib import Path
from rvw.common.proc import run_group


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--timeout',type=float,default=60)
    parser.add_argument('--depth',type=int,default=8)
    parser.add_argument('--mode',choices=('prove','bmc'),default='prove')
    parser.add_argument('--engine',choices=('smtbmc yices','abc pdr','abc bmc3'),default='smtbmc yices')
    args=parser.parse_args()
    here=Path(__file__).resolve().parent
    spec=importlib.util.spec_from_file_location('group',here.parents[1]/'scripts/prepare-check-group.py')
    group=importlib.util.module_from_spec(spec);spec.loader.exec_module(group)
    group.prepare(here/'out/clean',here/'out/clean/TinyOoo.checks.json',args.out,
        'freelist.conservation:rename',
        ['rename.'+name+':rename' for name in ('occupancy','disjoint','capacity','owners','chain')],depth=args.depth)
    job=args.out/'0/job.sby'
    job.write_text(job.read_text().replace('mode prove','mode '+args.mode).replace('smtbmc yices',args.engine))
    result=run_group(['nice','-n','15','sby','-f','-d','proof','job.sby'],
        cwd=args.out/'0',capture=True,timeout=args.timeout)
    (args.out/'proof.log').write_text(result.stdout+result.stderr)
    return result.returncode if result.returncode is not None and result.returncode>=0 else 1


if __name__=='__main__':
    raise SystemExit(main())
