"""Certify a smaller modulo counter against an exported concrete counter leaf."""
from argparse import Namespace
import contextlib
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import sys
from rvw.common.proc import run_group
from .contracts import assumption_inventory


def generate(plan):
    width, keep = plan['width'], plan['keep_bits']
    if type(width) is not int or type(keep) is not int or not 1 <= keep < width <= 256:
        raise ValueError('need 1 <= keep_bits < width <= 256')
    ports = plan.get('ports', {'clock': 'clk', 'reset': 'reset', 'enable': 'enable', 'count': 'count'})
    if set(ports) != {'clock', 'reset', 'enable', 'count'} or len(set(ports.values())) != 4:
        raise ValueError('ports must map four distinct clock/reset/enable/count names')
    for name in [plan['top'], *ports.values()]:
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name):
            raise ValueError('counter module and ports need simple identifiers')
    polarity = plan.get('reset_active', 'high')
    if polarity not in ('high', 'low'):
        raise ValueError('reset_active must be high or low')
    model = f'''module rvw_counter_small(input clk, reset, enable, output reg [{keep-1}:0] count);
always @(posedge clk) if(reset) count<=0; else if(enable) count<=count+1'b1;
endmodule
'''
    reset = 'reset' if polarity == 'high' else '!reset'
    wrapper = f'''module rvw_counter_relation(input clk, reset, enable);
wire [{width-1}:0] concrete_count;
wire [{keep-1}:0] abstract_count;
{plan['top']} concrete(.{ports['clock']}(clk), .{ports['reset']}({reset}),
  .{ports['enable']}(enable), .{ports['count']}(concrete_count));
rvw_counter_small abstract(.clk(clk), .reset(reset), .enable(enable), .count(abstract_count));
always @(posedge clk) if(!reset) assert(concrete_count[{keep-1}:0] == abstract_count);
endmodule
'''
    expected = {ports['clock']: ('input', 1), ports['reset']: ('input', 1),
                ports['enable']: ('input', 1), ports['count']: ('output', width)}
    return model, wrapper, expected


def run(args):
    from .cli import _flow
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        raise ValueError('timeout must be finite and positive')
    plan_path = Path(args.manifest).resolve()
    raw = plan_path.read_bytes()
    plan = json.loads(raw)
    model, wrapper, expected = generate(plan)
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out / 'manifest.json').write_bytes(raw)
    inputs, hashes = [], []
    for i, source in enumerate(plan['sources']):
        data = (plan_path.parent / source['path']).read_bytes()
        if sha256(data).hexdigest() != source['sha256'] or source.get('format', 'verilog') != 'verilog':
            raise ValueError('counter sources must be hash-pinned Verilog')
        if b'`include' in data or b'$readmem' in data:
            raise ValueError('counter sources must be self-contained')
        p = out / f'input{i}.sv'
        p.write_bytes(data)
        inputs.append(p)
        hashes.append(source['sha256'])
    if not inputs:
        raise ValueError('counter needs concrete RTL sources')
    script = 'read -formal ' + ' '.join(p.name for p in inputs) + '; prep -top ' + plan['top'] + '; write_json ports.json'
    proc = run_group(['yosys', '-Q', '-T', '-p', script], cwd=out, capture=True, timeout=args.timeout)
    (out / 'ports.log').write_text((proc.stdout or '') + (proc.stderr or ''))
    if proc.timed_out or proc.returncode:
        raise ValueError('cannot inspect concrete counter interface')
    design = json.loads((out / 'ports.json').read_text())
    ports = design['modules'][plan['top']]['ports']
    actual = {n: (p['direction'], len(p['bits'])) for n, p in ports.items()}
    if actual != expected:
        raise ValueError('concrete counter ports differ from declared widths and directions')
    if {'rvw_counter_small', 'rvw_counter_relation'} & design['modules'].keys():
        raise ValueError('concrete RTL collides with generated module names')
    assumptions = assumption_inventory(design)
    small, harness = out / 'abstract.sv', out / 'relation.sv'
    small.write_text(model)
    harness.write_text(wrapper)
    child = Namespace(verilog=[str(p) for p in inputs + [small, harness]], top='rvw_counter_relation',
                      clock='clk', reset='reset', reset_active='high', reset_cycles=1, free_reset=False,
                      event_model=False, event_clock=None, async_reset=False, checks=None,
                      depth=args.depth, mode='prove', engine=args.engine, timeout=args.timeout,
                      first_failure=True, cut=None, tie=None, out=str(out / 'proof'), json=False, project=None)
    with contextlib.redirect_stdout(sys.stderr):
        _flow('bmc', child)
    proof = json.loads((out / 'proof/result.json').read_text())
    certified = proof['status'] == 'pass' and proof.get('proof_kind') == 'unbounded' and not assumptions
    report = {'schema': 'rvw.formal-counter-quotient/1', 'status': 'pass' if certified else 'inconclusive',
              'proof_kind': 'unbounded_reset_qualified_counter_relation' if certified else 'none',
              'reason': 'relation_proved' if certified else 'source_assumptions_unqualified' if assumptions else 'obligation_failed' if proof['status'] == 'fail' else 'relation_unproved',
              'relation': f"abstract_count = concrete_count mod {2**plan['keep_bits']}",
              'concrete_width': plan['width'], 'abstract_width': plan['keep_bits'],
              'model_sha256': sha256(small.read_bytes()).hexdigest(), 'source_sha256': hashes,
              'manifest_sha256': sha256(raw).hexdigest(), 'source_assumptions': assumptions,
              'proof': 'proof/result.json', 'restrictions': proof.get('restrictions', []),
              'limits': 'Relation covers the supplied concrete counter leaf under the guarded reset/clock model. '
                        'The generated counter counts enabled cycles modulo its smaller width. '
                        'The proof uses the recorded initial-reset policy and covers projected low bits only. '
                        'No replacement of a wider design is performed. A refuted candidate is not a DUT bug.'}
    (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report) if args.json else str(out / 'result.json'))
    return 0 if certified else 1
