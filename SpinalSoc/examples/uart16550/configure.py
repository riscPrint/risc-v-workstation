#!/usr/bin/env python3
"""Bind the directed UART bench to an elaborated Spinal wrapper."""
import argparse
import json
from pathlib import Path

here=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--wrapper',required=True,type=Path)
parser.add_argument('--out',required=True,type=Path)
args=parser.parse_args()
manifest=json.loads((here/'bench.json').read_text())
manifest['top']='Uart16550Full'
manifest['sources']=[str(args.wrapper.resolve(strict=True)),str((here/'../../src/main/resources/rvwsoc/uart16550.sv').resolve())]
manifest['python_paths']=[str(here)]
with args.out.open('x') as stream:
    stream.write(json.dumps(manifest,indent=2)+'\n')
