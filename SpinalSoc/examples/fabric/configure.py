#!/usr/bin/env python3
"""Bind the four emitted native fabric fixtures to the independent VIP bench."""
import argparse
import json
from pathlib import Path

here=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--rtl',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
cases={'axi':'NativeAxiFabricFixture','tl':'NativeTlFabricFixture',
       'down':'NativeWidthDownFixture','up':'NativeWidthUpFixture'}
sources={name:(args.rtl/name/(top+'.v')).resolve(strict=True) for name,top in cases.items()}
args.out.mkdir(parents=True,exist_ok=False)
for name,top in cases.items():
    data=dict(schema='rvw.cocotb/1',name='native_'+name,backend='verilator',top=top,sources=[str(sources[name])],
              test_module='test_fabric',python_paths=[str(here)],requires=['timer'],
              clock=dict(signal='clk',period_ns=10),reset=dict(signal='reset',active=1,cycles=5))
    (args.out/(name+'.json')).write_text(json.dumps(data,indent=2)+'\n')
