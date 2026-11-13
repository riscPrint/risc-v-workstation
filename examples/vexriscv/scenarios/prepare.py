#!/usr/bin/env python3
"""Prepare a real CPU image and expose the existing composed peripheral ports."""
import argparse
import json
from pathlib import Path
import shutil

from rvw.formal.scenario_compile import compile_scenario
from rvw.soc.compose import compose
from rvw.soc.model import load

ROOT = Path(__file__).resolve().parents[3]


def prepare(out):
    out = Path(out).resolve()
    source = ROOT / 'SpinalSoc/examples/vex'
    data = json.loads(Path(__file__).with_name('scenario.json').read_text())
    compile_scenario(data, out, finisher=0x10001000)
    (out / 'scenario.json').write_text(json.dumps(data, indent=2) + '\n')
    shutil.copyfile(Path(__file__).with_name('test_scenario.py'), out / 'test_scenario.py')
    shutil.copyfile(source.parent / 'stub/link.ld', out / 'link.ld')
    spec = json.loads((source / 'compose.json').read_text())
    spec['map'] = str(source / 'soc.json')
    spec['devices']['finisher']['exports'] = ['done', 'code']
    (out / 'compose.json').write_text(json.dumps(spec, indent=2) + '\n')
    return out


def elaborate_input(out):
    out = Path(out).resolve()
    generated = ROOT / 'SpinalSoc/generated'
    compose(out / 'compose.json', generated, out / 'program.elf')
    model = load(ROOT / 'SpinalSoc/examples/vex/soc.json')
    probes, bases = [], {}
    for region in model['regions']:
        if region['kind'] != 'mmio' or region['name'] == 'finisher':
            continue
        name = region['name']
        bases[name] = region['base']
        fields = ['PADDR','PSEL','PENABLE','PWRITE','PWDATA','PRDATA','PREADY','PSLVERROR']
        packed = ' ## '.join(f'{name}.io.bus.{field}.asBits' for field in fields)
        probes += [f'  val {name}_probe = out(Bits({region["size"].bit_length()-1+69} bits))',
                   f'  {name}_probe := {packed}']
    scala = generated / 'ComposedSoc.scala'
    scala.write_text(scala.read_text().replace('\n}\nobject Generate', '\n' + '\n'.join(probes) + '\n}\nobject Generate'))
    (out / 'probe-bases.json').write_text(json.dumps(bases, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare','elaborate-input'])
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    (prepare if args.action == 'prepare' else elaborate_input)(args.out)
