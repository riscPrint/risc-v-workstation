#!/usr/bin/env python3
"""Export the real VexiiRiscv radix-2 unit and check unsigned M transactions."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess

from rvw.common.proc import run_group


def adapter(operation, divisor, operand_bits, implementation='DivRadix2'):
    if operation not in ('divu', 'remu'):
        raise ValueError('unsigned divide or remainder required')
    if not 1 <= operand_bits <= 32:
        raise ValueError('operand bits must be in 1..32')
    if implementation not in ('DivRadix2', 'DivRadix'):
        raise ValueError('unknown divider implementation')
    mask = (1 << operand_bits) - 1
    result = 'quotient' if operation == 'divu' else 'remainder'
    denominator = "32'd0" if divisor == 'zero' else f"(b & 32'h{mask:x})"
    return f"""module dut(input clk,reset,start,input [31:0] a,b,output [31:0] y,output done);
wire [31:0] quotient,remainder;
assign y={result};
{implementation} unit0(.clk(clk),.reset(reset),.io_flush(reset),
 .io_cmd_valid(start),.io_cmd_ready(),.io_cmd_payload_a(a & 32'h{mask:x}),
 .io_cmd_payload_b({denominator}),.io_cmd_payload_normalized(1'b0),
 .io_cmd_payload_iterations(5'd31),.io_rsp_valid(done),.io_rsp_ready(1'b1),
 .io_rsp_payload_result(quotient),.io_rsp_payload_remain(remainder));
endmodule
"""


def model(root, operation, divisor, operand_bits):
    models = root / 'SpinalChecks/c2rtl/models'
    text = (models / (operation + '32.c')).read_text().replace('#include "riscv_m.h"', '')
    mask = (1 << operand_bits) - 1
    b = '0ULL' if divisor == 'zero' else f'(b & {mask}ULL)'
    old = '32, a, b)'
    if old not in text:
        raise ValueError('reference call changed')
    return (models / 'riscv_m.h').read_text() + text.replace(old, f'32, (a & {mask}ULL), {b})')


def zero_smoke(root, rtl, out, implementation='DivRadix2'):
    source = out / 'zero-smoke.v'
    source.write_text(rtl.read_text() + adapter('divu', 'zero', 32, implementation) + '''
module tb;
reg clk=0,reset=1,start=0;reg[31:0]a=1,b=0;wire[31:0]y;wire done;
dut d(.*);
always #5 clk=~clk;
integer i;
initial begin
repeat(2) @(negedge clk); reset=0;
@(negedge clk);start=1;
@(negedge clk);start=0;
for(i=0;i<40;i=i+1) begin
@(negedge clk);
if(done)begin $display("RVW_SAMPLE cycle=%0d y=%08x",i+1,y);$finish;end
end
$fatal(1,"completion timeout");
end
endmodule
''')
    commands = [
        ['iverilog', '-g2012', '-s', 'tb', '-o', str(out / 'zero-smoke'), str(source)],
        ['vvp', str(out / 'zero-smoke')]]
    logs = []
    for command in commands:
        r = run_group([str(root / 'scripts/with-lock.sh'), 'vex-equiv', 'nice', '-n', '10', *command],
                      timeout=30, capture=True)
        logs.append((r.stdout or '') + (r.stderr or ''))
        if r.returncode:
            (out / 'zero-smoke.log').write_text('\n'.join(logs))
            return {'status': 'inconclusive', 'reason': 'native simulation failed'}
    (out / 'zero-smoke.log').write_text('\n'.join(logs))
    match = re.search(r'RVW_SAMPLE cycle=(\d+) y=([0-9a-fA-F]+)', logs[-1])
    if not match:
        return {'status': 'inconclusive', 'reason': 'no completion record'}
    value = int(match[2], 16)
    return {'status': 'match' if value == 0xffffffff else 'mismatch',
            'operation': 'divu', 'a': 1, 'b': 0, 'observed': value,
            'expected': 0xffffffff, 'cycles_after_start_removed': int(match[1]),
            'backend': 'icarus', 'proof_ran': False}


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--operations', default='divu,remu')
    p.add_argument('--divisor', choices=['full', 'zero'], default='full')
    p.add_argument('--operand-bits', type=int, default=32)
    p.add_argument('--timeout', type=float, default=180)
    p.add_argument('--build-timeout', type=float, default=180)
    p.add_argument('--max-latency', type=int, default=40)
    p.add_argument('--zero-smoke', action='store_true')
    p.add_argument('--low-area', action='store_true', help='use the core default bitpasta area configuration')
    p.add_argument('--implementation', choices=['DivRadix2', 'DivRadix'], default='DivRadix2')
    a = p.parse_args()
    root = Path(__file__).resolve().parents[3]
    source, out = a.source.resolve(), a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    build = out / 'generator'
    (build / 'src/main/scala').mkdir(parents=True)
    (build / 'project').mkdir()
    manifest = {'schema': 'rvw.vexii-div-unit/1', 'source_revision': revision,
                'spinal_version': '1.15.0', 'implementation': a.implementation, 'width': 32,
                'low_area': a.low_area if a.implementation == 'DivRadix2' else None,
                'radix': 2,
                'scope': 'real source unit; unsigned transactions; stable operands; no pipeline or ISA integration',
                'operand_bits': a.operand_bits, 'divisor': a.divisor,
                'max_latency': a.max_latency, 'source_files': {}, 'results': []}
    for name, marker in [('DivRadix.scala', 'object DivRadix4Tester'),
                         ('DivRadix2.scala', 'object DivRadix2TesterExhaustive')]:
        relative = 'src/main/scala/vexiiriscv/misc/' + name
        raw = subprocess.check_output(['git', '-C', str(source), 'show', revision + ':' + relative])
        text = raw.decode()
        if marker not in text:
            raise ValueError('test object boundary changed: ' + name)
        # Remove simulation entry points only. Keep all component definitions.
        selected = text.split(marker, 1)[0]
        (build / 'src/main/scala' / name).write_text(selected)
        manifest['source_files'][relative] = {'sha256': hashlib.sha256(raw).hexdigest(),
                                            'component_sha256': hashlib.sha256(selected.encode()).hexdigest()}
    (build / 'project/build.properties').write_text('sbt.version=1.10.7\n')
    (build / 'build.sbt').write_text("""scalaVersion := "2.13.14"
val spinalVersion = "1.15.0"
libraryDependencies ++= Seq(
 "com.github.spinalhdl" %% "spinalhdl-core" % spinalVersion,
 "com.github.spinalhdl" %% "spinalhdl-lib" % spinalVersion,
 "com.github.spinalhdl" %% "spinalhdl-sim" % spinalVersion,
 compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % spinalVersion))
fork := true
""")
    constructor = f'new vexiiriscv.misc.{a.implementation}(32, ' + (str(a.low_area).lower() + ')' if a.implementation == 'DivRadix2' else '2)')
    (build / 'src/main/scala/Export.scala').write_text("""import spinal.core._
object Export extends App {
 SpinalConfig(targetDirectory=args(0), defaultConfigForClockDomains=ClockDomainConfig(resetKind=SYNC))
  .generateVerilog(new vexiiriscv.misc.DivRadix2(32, false))
}
""".replace('new vexiiriscv.misc.DivRadix2(32, false)', constructor))
    command = [str(root / 'scripts/with-lock.sh'), 'sbt-equiv', 'nice', '-n', '10',
               'sbt', '-batch', '-J-Xmx2g', '-J-XX:ActiveProcessorCount=2', '-Dsbt.offline=true',
               'runMain Export ' + str(out / 'rtl')]
    r = run_group(command, cwd=build, timeout=a.build_timeout, capture=True)
    (out / 'export.log').write_text((r.stdout or '') + (r.stderr or ''))
    manifest['export'] = {'exit': r.returncode, 'timed_out': r.timed_out}
    (out / 'summary.json').write_text(json.dumps(manifest, indent=2) + '\n')
    if r.returncode:
        print(json.dumps(manifest))
        return 3
    rtl = out / ('rtl/' + a.implementation + '.v')
    manifest['rtl_sha256'] = hashlib.sha256(rtl.read_bytes()).hexdigest()
    if a.zero_smoke:
        manifest['zero_smoke'] = zero_smoke(root, rtl, out, a.implementation)
        (out / 'summary.json').write_text(json.dumps(manifest, indent=2) + '\n')
    for op in a.operations.split(','):
        directory = out / op
        directory.mkdir()
        (directory / 'dut.v').write_text(rtl.read_text() + adapter(op, a.divisor, a.operand_bits, a.implementation))
        (directory / 'model.c').write_text(model(root, op, a.divisor, a.operand_bits))
        command = [str(root / 'scripts/with-lock.sh'), 'vex-equiv', 'nice', '-n', '10',
                   str(root / 'rvw/.venv/bin/rvw'), 'formal', 'datapath',
                   '--rtl', str(directory / 'dut.v'), '--model', str(directory / 'model.c'),
                   '--width', '32', '--max-latency', str(a.max_latency),
                   '--timeout', str(a.timeout), '--out', str(directory / 'proof')]
        r = run_group(command, timeout=a.timeout + 10, capture=True)
        (directory / 'proof.log').write_text((r.stdout or '') + (r.stderr or ''))
        report = directory / 'proof/result.json'
        data = json.loads(report.read_text()) if report.exists() else {}
        manifest['results'].append({'operation': op, 'status': data.get('status', 'inconclusive'),
                                    'reason': data.get('reason'), 'wall_s': data.get('wall_s')})
        (out / 'summary.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))
    statuses = [r['status'] for r in manifest['results']]
    if manifest.get('zero_smoke', {}).get('status') == 'mismatch' or 'counterexample' in statuses:
        return 1
    if a.zero_smoke and manifest['zero_smoke']['status'] != 'match':
        return 3
    return 0 if statuses and all(s == 'proved' for s in statuses) else 3


if __name__ == '__main__':
    raise SystemExit(main())
