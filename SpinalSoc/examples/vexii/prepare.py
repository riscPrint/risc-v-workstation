#!/usr/bin/env python3
"""Capture ELFs and prepare inputs for the standalone Vexii SoC runner."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


def prepare(elfs, out, seed=31, max_cycles=100000):
    here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location('soc_vex_image',here.parent/'vex/adapter.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    out = Path(out).resolve()
    if out.exists(): raise ValueError('output directory must be new')
    if seed < 0 or max_cycles <= 0: raise ValueError('invalid seed or cycle limit')
    out.mkdir(parents=True)
    rows, inputs = [], []
    for index, source in enumerate(elfs):
        source = Path(source).resolve()
        captured = out/f'{index}.elf'; captured.write_bytes(source.read_bytes())
        image = out/f'{index}.hex'
        tohost = module.image(captured,image)
        rows.append(f'{image}\t{seed}\t{max_cycles}\t{tohost:x}\t{source.name}\n')
        inputs.append(dict(elf=str(source),sha256=hashlib.sha256(captured.read_bytes()).hexdigest(),tohost=tohost))
    if not rows: raise ValueError('at least one ELF is required')
    (out/'jobs.tsv').write_text(''.join(rows))
    (out/'inputs.json').write_text(json.dumps(dict(seed=seed,max_cycles=max_cycles,inputs=inputs),indent=2)+'\n')
    return out/'jobs.tsv'


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--elf',nargs='+',required=True); p.add_argument('--out',required=True)
    p.add_argument('--seed',type=int,default=31); p.add_argument('--max-cycles',type=int,default=100000)
    a=p.parse_args();print(prepare(a.elf,a.out,a.seed,a.max_cycles))
