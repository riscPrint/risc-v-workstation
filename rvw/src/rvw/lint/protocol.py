"""Selected event-enable CDC safety monitors over exported DUT ports."""
from pathlib import Path
import hashlib
import json
from rvw.formal import apps, common


def generate(plan):
    kind = plan.get('kind')
    if kind in ('pulse_capture', 'coherent_bus'):
        return generate_signal(plan)
    if kind not in ('handshake', 'async_fifo', 'reset_release'):
        raise ValueError('kind must be handshake, async_fifo or reset_release')
    top = apps.ident(plan['top'])
    inputs = dict(clk=1, reset=1, source_tick=1, destination_tick=1)
    outputs = dict(source_up=1, destination_up=1) if kind == 'reset_release' else dict(ready=1, valid=1, data_out=8)
    if kind != 'reset_release':
        inputs.update(push=1, pop=1, data_in=8, forward_choice=3, reverse_choice=3)
    ports = {n: dict(direction=d, width=w) for d, p in [('input', inputs), ('output', outputs)] for n, w in p.items()}
    header = 'module rvwcdc_top(' + ','.join(f'input [{w-1}:0] {n}' for n,w in inputs.items()) + ');\n'
    header += '\n'.join(f'wire [{w-1}:0] {n};' for n,w in outputs.items())
    header += f'\n{top} dut(' + ','.join(f'.{n}({n})' for n in ports) + ');\n'
    if kind == 'reset_release':
        body = '''reg first_seen, second_seen;
always @(posedge clk) begin
 if (reset) begin first_seen <= 0; second_seen <= 0; end
 else begin
   if (destination_tick) begin first_seen <= source_up; second_seen <= first_seen; end
   assert (!destination_up || (source_up && second_seen));
 end
end
'''
    else:
        capacity = 1 if kind == 'handshake' else 4
        body = f'''reg [7:0] expected [0:{capacity-1}];
integer count, head, tail;
wire send = source_tick && push && ready;
wire receive = destination_tick && pop && valid;
always @(posedge clk) begin
 if (reset) begin count <= 0; head <= 0; tail <= 0; end
 else begin
   assert (count >= 0 && count <= {capacity});
   if (send) begin
     assert (count < {capacity});
     expected[tail] <= data_in;
     tail <= (tail == {capacity-1}) ? 0 : tail + 1;
   end
   if (receive) begin
     assert (count > 0);
     assert (data_out == expected[head]);
     head <= (head == {capacity-1}) ? 0 : head + 1;
   end
   case ({{send,receive}})
     2'b10: count <= count + 1;
     2'b01: count <= count - 1;
   endcase
 end
end
'''
    return header + body + 'endmodule\n', ports


def run(args):
    path = Path(args.protocol).resolve()
    plan = json.loads(path.read_text())
    if plan.get('schema') != 'rvw.cdc-protocol/1' or set(plan) != {'schema', 'kind', 'top', 'verilog'}:
        raise ValueError('expected rvw.cdc-protocol/1 with kind, top and verilog')
    wrapper, ports = generate(plan)
    if not isinstance(plan['verilog'], list) or not plan['verilog']:
        raise ValueError('verilog must be a nonempty source list')
    sources = [(path.parent / p).resolve() for p in plan['verilog']]
    data = [p.read_bytes() for p in sources]
    if any(b'`include' in d for d in data):
        raise ValueError('export self-contained RTL without includes')
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    files = []
    for i, content in enumerate(data):
        p = out / f'input{i}.sv'; p.write_bytes(content); files.append(p)
    common.write_json(out / 'spec.json', plan)
    monitor = out / 'monitor.sv'; monitor.write_text(wrapper)
    if args.simulate:
        return simulate(args, plan, ports, files, monitor, sources, data, out)
    result = apps.flow([*files, monitor], 'rvwcdc_top', 'clk', 'reset', out / 'proof',
                       args.depth, args.engine, args.timeout, args.mode, {plan['top']: ports})
    report = dict(schema='rvw.cdc-protocol-result/1', kind=plan['kind'], status=result['status'],
                  proof_kind=result['proof_kind'], result='proof/result.json',
                  inputs=[dict(path=str(p), sha256=hashlib.sha256(d).hexdigest()) for p,d in zip(sources,data)],
                  activation='not_measured', model='global clock with independent event enables; old/new sampling choices are DUT inputs',
                  limits='Selected fixed-port CDC monitor. Safety or bounded destination-event response only. No fairness, pulse capture, analog metastability or CDC signoff. Reset checks use synchronous active-high global reset.')
    common.write_json(out / 'result.json', report)
    print(json.dumps(report, indent=2) if args.json else report['status'])
    return 0 if result['status'] == 'pass' else 1


def simulate(args, plan, ports, files, monitor, sources, data, out):
    import re
    import shutil
    from rvw.common.proc import run_group
    if not 1 <= args.simulate <= 1000000 or not 1 <= args.seed <= 2147483647:
        raise ValueError('simulation needs 1..1000000 samples and seed 1..2147483647')
    # Every assertion becomes fatal. A zero simulator exit alone is insufficient.
    text = re.sub(r'assert \((.*?)\);', r'assert (\1) else $fatal(1, "CDC protocol assertion");', monitor.read_text())
    monitor.write_text(text)
    inputs = {n:p for n,p in ports.items() if p['direction'] == 'input'}
    if plan['kind'] == 'pulse_capture':
        del inputs['pulse']
        inputs['launch'] = dict(direction='input', width=1)
    declarations = '\n'.join(f"reg [{p['width']-1}:0] {n} = 0;" for n,p in inputs.items())
    randomize = '\n'.join(f'{n} = $random(seed);' for n in inputs if n not in ('clk','reset'))
    tb = out / 'testbench.sv'
    tb.write_text('module testbench;\n' + declarations +
        '\nrvwcdc_top dut(' + ','.join(f'.{n}({n})' for n in inputs) + ');\n' +
        f'integer seed = {args.seed};\nalways #5 clk = ~clk;\ninitial begin\n' +
        'reset = 1; repeat (4) @(negedge clk); reset = 0;\n' +
        f'repeat ({args.simulate}) begin\n' + randomize + '\n@(negedge clk); end\n' +
        '$display("RVW_CDC_SIM_COMPLETE"); $finish; end\nendmodule\n')
    compiler, runtime = shutil.which('iverilog'), shutil.which('vvp')
    logs = []
    status = 'inconclusive'
    if compiler and runtime:
        executable = out / 'simulation'
        command = [compiler, '-g2012', '-s', 'testbench', '-o', str(executable), *map(str, files), str(monitor), str(tb)]
        built = run_group(command, timeout=args.timeout, capture=True)
        logs.append((built.stdout or '') + (built.stderr or ''))
        if built.returncode == 0 and not built.timed_out:
            run = run_group([runtime, str(executable)], timeout=args.timeout, capture=True)
            log = (run.stdout or '') + (run.stderr or ''); logs.append(log)
            if not run.timed_out:
                if run.returncode == 0 and 'RVW_CDC_SIM_COMPLETE' in log:
                    status = 'pass'
                elif 'CDC protocol assertion' in log:
                    status = 'fail'
    (out / 'simulation.log').write_text('\n'.join(logs))
    report = dict(schema='rvw.cdc-simulation/1', status=status, kind=plan['kind'],
                  seed=args.seed, requested_samples=args.simulate,
                  inputs=[dict(path=str(p), sha256=hashlib.sha256(d).hexdigest()) for p,d in zip(sources,data)],
                  limits='Seeded digital old/new perturbation only. No proof, analog metastability, MTBF or signoff.')
    common.write_json(out / 'result.json', report)
    print(json.dumps(report, indent=2) if args.json else status)
    return 0 if status == 'pass' else 1


def generate_signal(plan):
    top = apps.ident(plan['top'])
    pulse = plan['kind'] == 'pulse_capture'
    inputs = dict(clk=1, reset=1, source_tick=1, destination_tick=1, forward_choice=3)
    inputs['pulse' if pulse else 'launch'] = 1
    outputs = dict(captured=1) if pulse else dict(pair=2)
    ports = {n:dict(direction=d, width=w) for d,p in [('input',inputs),('output',outputs)] for n,w in p.items()}
    wrapper_inputs = {n:w for n,w in inputs.items() if n != 'pulse'}
    if pulse:
        wrapper_inputs['launch'] = 1
    header = 'module rvwcdc_top(' + ','.join(f'input [{w-1}:0] {n}' for n,w in wrapper_inputs.items()) + ');\n'
    header += '\n'.join(f'wire [{w-1}:0] {n};' for n,w in outputs.items())
    if pulse:
        header += '\nreg fired, pending; reg [2:0] age;\nwire pulse = source_tick && launch && !fired;\n'
    header += f'\n{top} dut(' + ','.join(f'.{n}({n})' for n in ports) + ');\n'
    if pulse:
        body = """always @(posedge clk) begin
 if (reset) begin fired <= 0; pending <= 0; age <= 0; end
 else begin
   if (pulse) begin fired <= 1; pending <= 1; end
   if (captured) begin assert (pending); pending <= 0; end
   if (pending && destination_tick && !captured) begin
     assert (age < 4);
     if (age < 5) age <= age + 1;
   end
 end
end
"""
    else:
        body = 'always @(posedge clk) if (!reset) assert (pair == 0 || pair == 3);\n'
    return header + body + 'endmodule\n', ports
