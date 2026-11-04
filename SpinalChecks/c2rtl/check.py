#!/usr/bin/env python3
"""Exhaustive small unsigned C functions against combinational RTL."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil

from rvw.common.proc import run_group

# Closed set: state, formal constraints, memories, and unknown cells are refused.
COMB = {"$" + x for x in (
    "add sub mul div mod pow shl shr sshl sshr shift shiftx lt le eq ne eqx nex ge gt "
    "not pos neg and or xor xnor reduce_and reduce_or reduce_xor reduce_xnor reduce_bool "
    "logic_not logic_and logic_or mux pmux bmux demux slice concat lut"
).split()}


def validate_design(data, width):
    module = data['modules']['dut']
    ports = module['ports']
    if set(ports) != {'a', 'b', 'y'}:
        raise ValueError('dut must have only a, b, y ports')
    for name, direction in [('a', 'input'), ('b', 'input'), ('y', 'output')]:
        p = ports[name]
        if p['direction'] != direction or len(p['bits']) != width or p.get('signed', 0):
            raise ValueError('ports must be unsigned and match --width')
    if any(c['type'] not in COMB for c in module.get('cells', {}).values()):
        raise ValueError('state, assumptions, assertions or unsupported cells in dut')
    if any('init' in n.get('attributes', {}) for n in module.get('netnames', {}).values()):
        raise ValueError('initial state in dut')


def parse_table(text, width):
    rows = [tuple(map(int, line.split())) for line in text.splitlines()]
    expected = [(a, b) for a in range(1 << width) for b in range(1 << width)]
    if len(rows) != len(expected) or any(len(row) != 3 for row in rows):
        raise ValueError('C model did not emit a complete table')
    if [(r[0], r[1]) for r in rows] != expected:
        raise ValueError('C model table input order is invalid')
    if any(not 0 <= r[2] < (1 << width) for r in rows):
        raise ValueError('C model result exceeds --width')
    return rows


def run(args):
    out = Path(args.out).resolve()
    # Fresh directories prevent stale status or trace reuse. Never delete user data.
    out.mkdir(parents=True, exist_ok=False)
    result = dict(schema='rvw.c2rtl/1', status='inconclusive', backend='sby',
                  width=args.width, signed=False, latency_cycles=0, handshake='none',
                  depth=1, input_pairs=None, artifacts=str(out))
    commands = []
    selected = {}
    stamps = {}

    def command(argv, name):
        commands.append(argv)
        argv = [selected.get(argv[0], argv[0]), *argv[1:]]
        r = run_group(argv, cwd=out, timeout=args.timeout, capture=True)
        (out / (name + '.log')).write_text((r.stdout or '') + (r.stderr or ''))
        if r.timed_out or r.returncode:
            raise ValueError(f'{name} failed or timed out; see {name}.log')
        return r.stdout or ''

    try:
        if not 1 <= args.width <= 4 or not 0 < args.timeout <= 3600:
            raise ValueError('width must be 1..4; timeout must be in (0, 3600]')
        result['input_pairs'] = 1 << (2 * args.width)
        result['tool_files'] = {}
        for tool in ('clang', 'yosys', 'sby', 'yices-smt2', 'yosys-smtbmc', 'yosys-witness'):
            path = shutil.which(tool)
            if not path:
                raise ValueError(f'missing native tool: {tool}')
            path = str(Path(path).resolve())
            selected[tool] = path
            stamps[path] = Path(path).stat()
            result['tool_files'][tool] = dict(path=path,
                sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest())
        result['environment'] = {name: os.environ.get(name) for name in
            ('PATH', 'YOSYS_DATDIR', 'DYLD_LIBRARY_PATH', 'LD_LIBRARY_PATH')}
        result['tools'] = {t: command([t, '--version' if t != 'yosys' else '-V'], t).strip()
                           for t in ('clang', 'yosys', 'sby', 'yices-smt2')}
        result['inputs'] = {}
        for source, target in [(args.model, 'model.c'), (args.rtl, 'dut.v')]:
            raw = Path(source).read_bytes()
            (out / target).write_bytes(raw)
            result['inputs'][target] = dict(source=str(Path(source).resolve()),
                                           sha256=hashlib.sha256(raw).hexdigest())
            # This first flow accepts one self-contained file per language.
            if re.search(rb'^\s*#\s*include', raw, re.M) and target == 'model.c':
                raise ValueError('model.c must use the driver uint32_t type without includes')
            if target == 'dut.v' and re.search(rb'`include|\$readmem', raw):
                raise ValueError('RTL includes and external memory files are not supported')
        width = args.width
        (out / 'driver.c').write_text('''#include <stdint.h>
#include <stdio.h>
#include "model.c"
_Static_assert(_Generic(&reference, uint32_t (*)(uint32_t, uint32_t): 1, default: 0),
               "reference must have the exact unsigned integer interface");
int main(void) {
  for (uint32_t a=0; a<LIMIT; ++a)
    for (uint32_t b=0; b<LIMIT; ++b)
      printf("%u %u %u\\n", a, b, reference(a,b));
  return 0;
}
'''.replace('LIMIT', str(1 << width)))
        command(['clang', '-std=c11', '-O0', '-Wall', '-Wextra', '-Werror',
                 '-fsanitize=undefined', '-fno-sanitize-recover=all',
                 'driver.c', '-o', 'reference'], 'compile')
        table = command([str(out / 'reference')], 'table')
        rows = parse_table(table, width)
        command(['yosys', '-Q', '-T', '-p',
                 'read_verilog -formal dut.v; hierarchy -check -top dut; proc; flatten; '
                 'check -assert; write_json dut.json'], 'elaborate')
        validate_design(json.loads((out / 'dut.json').read_text()), width)
        cases = '\n'.join(f"{2*width}'d{(a << width) | b}: expected = {width}'d{y};"
                          for a, b, y in rows)
        (out / 'miter.sv').write_text(f'''module miter(input [{width-1}:0] a,b);
wire [{width-1}:0] y;
reg [{width-1}:0] expected;
dut u(.a(a),.b(b),.y(y));
always @* begin
  expected = 0;
  case ({{a,b}})
{cases}
  endcase
  assert(y == expected);
end
endmodule
''')
        (out / 'check.sby').write_text('''[options]
mode bmc
depth 1
[engines]
smtbmc yices
[script]
read_verilog -formal dut.v miter.sv
prep -top miter
[files]
dut.v
miter.sv
''')
        # FAIL is a valid check result, so inspect its return code separately.
        r = run_group([selected['sby'], '-f', 'check.sby'], cwd=out, timeout=args.timeout, capture=True)
        commands.append(['sby', '-f', 'check.sby'])
        (out / 'sby.log').write_text((r.stdout or '') + (r.stderr or ''))
        status_file = out / 'check/status'
        tokens = status_file.read_text().split() if status_file.exists() else []
        status = tokens[0] if tokens else ''
        traces = list(out.glob('check/engine_*/trace_tb.v'))
        if not r.timed_out and status == 'PASS' and r.returncode == 0:
            result['status'] = 'proved'
        elif not r.timed_out and status == 'FAIL' and r.returncode == 2 and traces:
            result['status'] = 'counterexample'
            result['traces'] = [str(p.relative_to(out)) for p in traces]
        else:
            result['reason'] = 'solver did not produce complete proof or counterexample evidence'
    except (OSError, ValueError, KeyError) as exc:
        result['reason'] = str(exc)
    try:
        changed = any(any(getattr(Path(path).stat(), k) != getattr(stamp, k)
                          for k in ('st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns'))
                      for path, stamp in stamps.items())
        if changed:
            raise ValueError('tool file changed during check')
    except (OSError, ValueError) as exc:
        result['status'] = 'inconclusive'
        result['reason'] = str(exc)
    result['commands'] = commands
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', required=True)
    p.add_argument('--rtl', required=True)
    p.add_argument('--width', type=int, default=4)
    p.add_argument('--timeout', type=float, default=30, help='seconds per native command')
    p.add_argument('--out', required=True, help='new output directory')
    args = p.parse_args()
    try:
        result = run(args)
    except OSError as exc:
        result = dict(status='inconclusive', reason=str(exc))
    print(json.dumps(result, indent=2))
    return {'proved': 0, 'counterexample': 1, 'inconclusive': 3}[result['status']]


if __name__ == '__main__':
    raise SystemExit(main())
