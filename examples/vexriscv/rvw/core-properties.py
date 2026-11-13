#!/usr/bin/env python3
"""Prepare one real-core SBY job per Scala DSL assertion."""
import argparse
import json
from pathlib import Path
import re

from rvw.formal.temporal import lower


def prepare(rtl, out, depth=12):
    rtl, out = Path(rtl), Path(out)
    out.mkdir(parents=True, exist_ok=False)
    source = (rtl / 'VexTop.v').read_text()
    statements = (rtl / 'properties.sv').read_text().splitlines()
    # Spinal's Verilog has a timescale directive. It is irrelevant to formal.
    source = re.sub(r'^`timescale[^\n]*', '', source, flags=re.M)
    end = source.index('endmodule')
    reset = '''
reg [1:0] property_reset_age = 0;
always @(posedge clk) if (property_reset_age != 3) property_reset_age <= property_reset_age + 1'b1;
always @* assume(reset == (property_reset_age < 2));
'''
    manifest = ['core = "vexriscv"', 'config = "rv32im-dsl"']
    inventory = []
    for statement in statements:
        name = statement.split(':', 1)[0]
        if ': assert property' not in statement:
            continue
        directory = out / name
        directory.mkdir()
        monitor, props = lower('module Properties;\n' + statement + '\nendmodule')
        monitor = monitor.removeprefix('module Properties;').removesuffix('endmodule')
        model = source[:end] + reset + monitor + '\n' + source[end:]
        (directory / 'model.sv').write_text(model)
        (directory / 'job.sby').write_text(
            f'[options]\nmode bmc\ndepth {depth}\n\n[engines]\nsmtbmc yices\n\n'
            '[script]\nread_verilog -formal -sv model.sv\nprep -top VexTop\nasync2sync\ndffunmap\n\n'
            '[files]\nmodel.sv\n')
        manifest += ['', '[[property]]', f'id = "{name}"', f'sby = "{name}/job.sby"',
                     'top = "VexTop"', 'assumptions = ["two reset clocks; other inputs arbitrary"]']
        inventory += props
    (out / 'regress.toml').write_text('\n'.join(manifest) + '\n')
    (out / 'properties.json').write_text(json.dumps(inventory, indent=2) + '\n')
    return inventory


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rtl', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--depth', type=int, default=12)
    args = parser.parse_args()
    prepare(args.rtl, args.out, args.depth)
