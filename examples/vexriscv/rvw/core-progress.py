#!/usr/bin/env python3
"""Observe the project-owned eventual pipeline release property on real RTL."""
import argparse
import importlib.util
import json
import re
from pathlib import Path

from rvw.formal.live_sim import rewrite
from rvw.common.proc import run_group
from rvw.formal.liveness import run as formal_run
from argparse import Namespace


def instrument(source, statements):
    lowered, props = rewrite('module Properties;\n'+statements+'\nendmodule', 'Properties', simulation=True)
    lowered = lowered.removeprefix('module Properties;').removesuffix('endmodule')
    for prop in props:
        prefix = prop['monitor']
        prop['pending_required'] = True
        lowered = lowered.replace(f'reg {prefix}_tick=0;', f'wire {prefix}_tick=clk;')
        counters = []
        for outcome in ['pass','fail','cover','miss','activated']:
            name = prefix + '_' + outcome
            counters += [f'reg [63:0] {name}=0;',
                         f'final $display("RVW_COUNT {prefix} {outcome} %0d", {name});']
            action = f'$display("RVW_SVA {prefix} {prop["kind"]} {outcome}");'
            lowered = lowered.replace(action, name + ' = ' + name + ' + 1;')
        # The project property is Boolean, overlapped and guards startup reset.
        # Its native monitor sets total=pending+request before testing response.
        assignment = re.search(re.escape(prefix+'_total') + r' = '+re.escape(prefix+'_pending')+r' \+ (.*);', lowered)
        if not assignment:
            raise ValueError('missing request accounting')
        counters += [f'always @(posedge clk) if ({assignment[1]}) {prefix}_activated <= {prefix}_activated + 1;',
                     f'final $display("RVW_PENDING {prefix} %0d", {prefix}_pending);']
        location = re.search(r'rvw-source: ([^\n]+):(\d+)', statements)
        prop['source'] = dict(file=location[1], line=int(location[2])) if location else None
        declarations = [line for line in counters if line.startswith('reg ')]
        reporting = [line for line in counters if not line.startswith('reg ')]
        lowered = '\n'.join(declarations) + '\n' + lowered + '\n' + '\n'.join(reporting)
    source = re.sub(r'^`timescale[^\n]*', '', source, flags=re.M)
    end = source.index('endmodule')
    return source[:end] + lowered + '\n' + source[end:], props


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['sim','formal'])
    parser.add_argument('--rtl', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('program', type=Path, nargs='*')
    args = parser.parse_args()
    if args.action == 'sim':
        spec = importlib.util.spec_from_file_location('core_sim', Path(__file__).with_name('core-properties-sim.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        statements = (args.rtl/'liveness.sv').read_text()
        module.instrument = lambda source, _: instrument(source, statements)
        raise SystemExit(module.run(args.rtl.resolve(), args.program, args.out.resolve()))
    args.out.mkdir(parents=True)
    source = re.sub(r'^`timescale[^\n]*', '', (args.rtl/'VexTop.v').read_text(), flags=re.M)
    end = source.index('endmodule')
    source = source[:end] + (args.rtl/'liveness.sv').read_text() + '\n' + source[end:]
    (args.out/'raw.sv').write_text(source)
    with (args.out/'source.sv').open('w') as target, (args.out/'preprocess.log').open('w') as log:
        process = run_group(['nice','-n','10','verilator','-E','-P','-DSYNTHESIS',
                             str(args.out/'raw.sv')], stdout=target, stderr=log, timeout=30)
    if process.returncode:
        raise RuntimeError('preprocessing failed; see preprocess.log')
    try:
        formal_run(Namespace(source=str(args.out/'source.sv'), top='VexTop', out=str(args.out/'proof'),
                             run=True, timeout=60, backend='l2s', reset='reset',
                             engine='smtbmc:yices', mode='bmc', depth=12))
    except ValueError as error:
        if str(error) != 'l2s adapter needs zero-based descending net ranges':
            raise
        result = dict(status='unsupported', reason=str(error),
                      scope='native adapter restriction; no liveness proof')
        (args.out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result))
    exported = args.out/'proof/l2s-0/proof'
    if (exported/'module_ports.il').exists():
        import shutil
        directory = args.out/'regress-job'
        directory.mkdir()
        with (directory/'export.log').open('w') as log:
            process = run_group(['nice','-n','10','yosys','-Q','-T','-p',
                'read_rtlil '+str((exported/'module_ports.il').resolve())+
                '; write_verilog -noattr '+str((directory/'design.sv').resolve())],
                stdout=log, stderr=log, timeout=30)
        if process.returncode:
            raise RuntimeError('regression export failed; see export.log')
        shutil.copyfile(exported/'rvw_formal_top.sv',directory/'wrapper.sv')
        # write_verilog emits this formal primitive as an escaped module cell.
        # Recreate its per-sample nondeterminism, with the original WIDTH.
        (directory/'primitives.sv').write_text(
            r'module \$anyseq #(parameter WIDTH=1)(output [WIDTH-1:0] Y); assign Y=$anyseq; endmodule'+'\n')
        (directory/'job.sby').write_text('[options]\nmode bmc\ndepth 12\n\n[engines]\nsmtbmc yices\n\n'
            '[script]\nread_verilog -formal -sv design.sv wrapper.sv primitives.sv\nprep -top rvw_formal_top\n\n'
            '[files]\ndesign.sv\nwrapper.sv\nprimitives.sv\n')
        activation = directory/'activation'
        activation.mkdir()
        model = (args.rtl/'VexTop.v').read_text().replace('module VexTop', 'module rvw_formal_top', 1)
        end = model.index('endmodule')
        cover = """
reg startup_done=0;
always @(posedge clk) startup_done<=1;
always @* assume(reset == !startup_done);
always @(posedge clk) cover(!reset && property_stage0_valid && property_stage0_stuck);
"""
        (activation/'model.sv').write_text(model[:end]+cover+model[end:])
        (activation/'job.sby').write_text('[options]\nmode cover\ndepth 12\n\n[engines]\nsmtbmc yices\n\n'
            '[script]\nread_verilog -formal -sv model.sv\nprep -top rvw_formal_top\nasync2sync\ndffunmap\n\n'
            '[files]\nmodel.sv\n')
        location = re.search(r'rvw-source: ([^\n]+):(\d+)',(args.rtl/'liveness.sv').read_text())
        (args.out/'regress.toml').write_text('[[property]]\n'
            'id = "stage0_eventual_release"\nsby = "regress-job/job.sby"\ntop = "rvw_formal_top"\n'
            'activation_sby = "regress-job/activation/job.sby"\n'
            'assumptions = ["one startup reset clock; no progress fairness; bounded lasso search"]\n'
            + (f'source = {{ file = "{location[1]}", line = {location[2]} }}\n' if location else ''))
