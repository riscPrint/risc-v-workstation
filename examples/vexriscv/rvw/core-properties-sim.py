#!/usr/bin/env python3
"""Compile Scala-emitted properties into the example ISA simulation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re

from rvw.common.proc import run_group
from rvw.cosim.elf import Elf
from rvw.formal.temporal import lower


def instrument(source, statements):
    source = re.sub(r'^`timescale[^\n]*', '', source, flags=re.M)
    end = source.index('endmodule')
    monitor, properties = lower('module Properties;\n' + statements + '\nendmodule', simulation=True)
    monitor = monitor.removeprefix('module Properties;').removesuffix('endmodule')
    model = source[:end] + monitor + '\n' + source[end:]
    counters = []
    for prop in properties:
        prefix = prop['monitor']
        for outcome in ('pass', 'fail', 'cover', 'miss', 'activated'):
            name = prefix + '_' + outcome
            action = f'$display("RVW_SVA {prefix} {prop["kind"]} {outcome}");'
            if outcome == 'activated':
                action = f'$display("RVW_ACTIVATE {prefix}");'
            if action in model:
                model = model.replace(action, name + ' <= ' + name + ' + 1;')
            counters += [f'reg [63:0] {name} = 0;',
                         f'final $display("RVW_COUNT {prefix} {outcome} %0d", {name});']
    end = model.index('endmodule')
    return model[:end] + '\n'.join(counters) + '\n' + model[end:], properties


def run(rtl, programs, out, samples=False):
    out.mkdir(parents=True, exist_ok=False)
    model, props = instrument((rtl / 'VexTop.v').read_text(), (rtl / 'properties.sv').read_text())
    (out / 'simulation.sv').write_text(model)
    command = ['nice', '-n', '10', 'verilator', '--cc', '--exe', '--build', '-j', '4',
               '-Wno-fatal', '--top-module', 'VexTop', '--Mdir', 'obj',
               'simulation.sv', str(Path(__file__).with_name('core-properties.cpp'))]
    with (out / 'compile.log').open('w') as log:
        proc = run_group(command, cwd=out, stdout=log, stderr=log, timeout=180)
    if proc.returncode:
        raise RuntimeError('Verilator compile failed: ' + str(out / 'compile.log'))
    summary = []
    for program in programs:
        elf = Elf(program)
        if elf.xlen != 32 or elf.entry != 0x80000000 or 'tohost' not in elf.symbols:
            raise ValueError('expected RV32 example ELF with tohost')
        directory = out / program.name
        directory.mkdir()
        image = bytearray(16 * 1024 * 1024)
        for address, data, size in elf.segments:
            offset = address - 0x80000000
            if offset < 0 or offset + size > len(image):
                raise ValueError('ELF outside example RAM')
            image[offset:offset + len(data)] = data
        memory = directory / 'memory.bin'
        memory.write_bytes(image)
        with (directory / 'run.log').open('w') as log:
            proc = run_group(['nice', '-n', '10', str(out / 'obj/VVexTop'), str(memory),
                              str(elf.symbols['tohost'])], stdout=log, stderr=log, timeout=30,
                              env=dict(os.environ, **({'RVW_PROPERTY_TRACE': str(directory / 'samples.jsonl')} if samples else {})))
        memory.unlink()
        text = (directory / 'run.log').read_text()
        observations = {}
        for monitor, outcome, value in re.findall(r'RVW_COUNT (\w+) (\w+) (\d+)', text):
            observations.setdefault(monitor, {})[{'pass': 'passed', 'fail': 'failed', 'cover': 'covered', 'miss': 'missed', 'activated': 'activated'}[outcome]] = int(value)
        pending = {monitor: int(value) for monitor, value in re.findall(r'RVW_PENDING (\w+) (\d+)', text)}
        checks = [dict(pending=pending.get(p['monitor'], 0), id=p['id'], kind=p['kind'], source=p.get('source'), **observations.get(p['monitor'], {})) for p in props]
        complete = all(set(observations.get(p['monitor'], {})) == {'passed', 'failed', 'covered', 'missed', 'activated'} for p in props)
        complete = complete and all(not p.get('pending_required') or p['monitor'] in pending for p in props)
        failed = sum(p.get('failed', 0) for p in checks if p['kind'] == 'assert')
        totals = re.search(r'RVW_PROGRAM (\d+) (\d+) (\d+)', text)
        result = dict(schema='rvw.run/1', core='vexriscv', config='rv32im-dsl',
                      status=('inconclusive' if any(pending.values()) else 'pass') if proc.returncode == 0 and complete and not failed else 'fail',
                      program_status='pass' if proc.returncode == 0 else 'fail',
                      cycles=int(totals[1]) if totals else 0, instret=int(totals[2]) if totals else 0,
                      assertions=checks, elf_sha256=hashlib.sha256(program.read_bytes()).hexdigest(),
                      source={'rtl_sha256': hashlib.sha256(model.encode()).hexdigest()},
                      artifacts={'log': 'run.log', 'coverage': 'coverage.dat'},
                      scope='finite ISA simulation with compiled temporal monitors')
        (directory / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        coverage = []
        for index, p in enumerate(checks):
            key = f'\x01f\x02simulation.sv\x01l\x021\x01page\x02sva-{p["kind"]}\x01o\x02{index}:{p["id"]}'
            coverage.append(f"C '{key}' {p.get('covered' if p['kind'] == 'cover' else 'passed', 0)}")
        (directory / 'coverage.dat').write_text('\n'.join(coverage) + '\n')
        summary.append(dict(program=program.name, **result))
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return 0 if summary and all(row['status'] == 'pass' for row in summary) else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rtl', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('program', type=Path, nargs='+')
    parser.add_argument('--samples', action='store_true', help='capture pre-edge project signals for candidate mining')
    args = parser.parse_args()
    raise SystemExit(run(args.rtl.resolve(), args.program, args.out.resolve(), args.samples))
