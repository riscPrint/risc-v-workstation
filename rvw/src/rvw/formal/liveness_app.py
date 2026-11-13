"""Reduce finite-state response liveness with justice to safety."""
import json
import re
from pathlib import Path
from .apps import ident


def monitor(state, request, response, fairness, clock, reset):
    """A nondeterministic loop snapshot detects an accepting bad lasso.

    Snapshot the DUT state and outstanding obligation. Every justice predicate
    must occur on the nonempty loop. Response must remain absent on that loop.
    """
    if not state:
        state = ["1'b0"]
    n = len(state)
    q = '{' + ', '.join(state) + '}'
    lines = [f'(* anyseq *) reg rvwl_save;', 'reg rvwl_pending = 0;',
             'reg rvwl_tracking = 0;', f'reg [{n-1}:0] rvwl_snapshot;',
             f'always @(posedge {clock}) begin',
             f' if ({reset}) begin rvwl_pending <= 0; rvwl_tracking <= 0; end',
             ' else begin',
             f' rvwl_pending <= (rvwl_pending || ({request})) && !({response});',
             f' if (!rvwl_tracking && rvwl_save && rvwl_pending && !({response})) begin',
             f' rvwl_tracking <= 1; rvwl_snapshot <= {q}; end',
             f' if ({response}) rvwl_tracking <= 0;', ' end end']
    for i, expr in enumerate(fairness):
        lines += [f'reg rvwl_fair{i} = 0;', f'always @(posedge {clock}) begin',
                  f' if ({reset}) rvwl_fair{i} <= 0;',
                  f' else if (!rvwl_tracking) rvwl_fair{i} <= rvwl_save && rvwl_pending && !({response}) && ({expr});',
                  f' else if ({expr}) rvwl_fair{i} <= 1; end']
    fair = ' && '.join(f'rvwl_fair{i}' for i, f in enumerate(fairness)) or "1'b1"
    lines += [f'always @(posedge {clock}) if (!{reset})',
              f' assert (!(rvwl_tracking && rvwl_pending && !({response}) && ({q} == rvwl_snapshot) && ({fair})));']
    return '\n'.join(lines)


def state_bits(module):
    """Use every state bit. Refuse memory, unknown cells and other state types."""
    aliases = {}
    for name, net in module['netnames'].items():
        if name.startswith('rvwl_'):
            raise ValueError('reserved rvwl_ signal')
        for i, bit in enumerate(net['bits']):
            if isinstance(bit, int):
                aliases.setdefault(bit, f'\\{name} [{i}]' if len(net['bits']) > 1 else f'\\{name} ')
    state = set()
    for cell in module.get('cells', {}).values():
        kind = cell['type']
        if kind == '$dff':
            if int(cell['parameters']['CLK_POLARITY'], 2) != 1:
                raise ValueError('falling-edge state unsupported')
            state.update(cell['connections']['Q'])
        elif kind in ('$live', '$fair'):
            raise ValueError('declare fairness and response in the app plan')
        elif kind.startswith(('$mem', '$adff', '$aldff', '$dlatch', '$ff', '$sdff', '$dffe', '$dff', '$sr', '$fsm', '$anyinit')) or not kind.startswith('$'):
            raise ValueError('unsupported state or black box: ' + kind)
    if not state <= aliases.keys():
        raise ValueError('state bits lack RTL names')
    return [aliases[b] for b in sorted(state)]


def run(args):
    from rvw.common.capture import Capture
    from rvw.common.proc import run_group
    from . import apps, common
    if args.timeout <= 0 or args.depth < 2:
        raise ValueError('timeout must be positive and depth at least two')
    path = Path(args.manifest).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    capture = Capture(out / 'inputs')
    plan = json.loads(capture.file(path).copy.read_text())
    top, clock, reset = (ident(plan[k]) for k in ('top', 'clock', 'reset'))
    if plan.get('schema') != 'rvw.liveness-app/1':
        raise ValueError('expected rvw.liveness-app/1')
    sources = [capture.file(path.parent / p).copy for p in plan['verilog']]
    if any('`include' in p.read_text() for p in sources):
        raise ValueError('export self-contained RTL first')
    yosys = capture.tool('yosys')
    flat, metadata = out / 'flat.v', out / 'flat.json'
    script = '; '.join(['read_verilog -formal -sv ' + ' '.join(json.dumps(str(p)) for p in sources),
        f'prep -top {top} -flatten', 'memory_map', 'opt_clean', 'dffunmap', 'chformal -remove -assert -cover',
        'write_json ' + json.dumps(str(metadata)), 'write_verilog -noattr ' + json.dumps(str(flat))])
    proc = run_group([str(yosys.path), '-Q', '-T', '-p', script], capture=True, timeout=args.timeout)
    (out / 'export.log').write_text((proc.stdout or '') + (proc.stderr or ''))
    if proc.returncode:
        raise ValueError('liveness model export failed')
    module = json.loads(metadata.read_text())['modules'][top]
    # One input clock must drive every state element.
    clk = module['ports'][clock]['bits']
    if any(c['connections']['CLK'] != clk for c in module['cells'].values() if c['type'] == '$dff'):
        raise ValueError('liveness needs one clock')
    ports = module['ports']
    def expression(value):
        if not isinstance(value, str) or re.search(r'[^A-Za-z0-9_ ()!&|^~<>=]', value):
            raise ValueError('unsupported Boolean expression')
        if any(n not in ports for n in re.findall(r'[A-Za-z_][A-Za-z0-9_]*', value)):
            raise ValueError('liveness expressions need top ports')
        return value
    request, response = (expression(plan[k]) for k in ('request', 'response'))
    fairness = [expression(f) for f in plan.get('fairness', [])]
    bits = state_bits(module)
    source = flat.read_text()
    source = source.replace('endmodule', monitor(bits, request, response, fairness, clock, reset) + '\nendmodule')
    instrumented = out / 'l2s.sv'; instrumented.write_text(source)
    result = apps.flow([instrumented], top, clock, reset, out / 'proof', args.depth,
                       args.engine, args.timeout, args.mode)
    # Fairness on DUT outputs or internal state, or under source assumptions, can exclude the
    # hung loop itself (a unit stuck busy with fairness `!busy`). Keep such a pass inconclusive.
    inputs = {n for n, p in ports.items() if p['direction'] == 'input'} - {clock, reset}
    unchecked = [f for f in fairness if not set(re.findall(r'[A-Za-z_][A-Za-z0-9_]*', f)) or
                 not set(re.findall(r'[A-Za-z_][A-Za-z0-9_]*', f)) <= inputs]
    assumed = any(c['type'] == '$assume' or (c['type'] == '$check' and c.get('parameters', {}).get('FLAVOR') == 'assume')
                  for c in module['cells'].values())
    feasibility = 'not_checked' if unchecked or (fairness and assumed) else 'free_inputs' if fairness else 'no_fairness'
    if result['status'] == 'pass' and feasibility == 'not_checked':
        result = dict(result, status='inconclusive', proof_kind='none')
    report = {'schema': 'rvw.liveness-app-result/1', 'status': result['status'], 'fairness_check': feasibility,
              'proof_kind': 'liveness_to_safety' if result['status'] == 'pass' and result['proof_kind'] != 'bounded' else ('bounded_lasso_search' if args.mode == 'bmc' else 'lasso_counterexample' if result['status'] == 'fail' else 'none'),
              'state_bits': len(bits), 'fairness': fairness, 'request': request, 'response': response,
              'result': 'proof/result.json', 'input_capture': capture.record(),
              'limits': 'Single synchronous finite-state RTL. Justice is conditional. A proof rules out fair infinite paths with an outstanding request and no response. Fairness feasibility is not established. A bounded pass cannot prove liveness. No existential CTL deadlock claim.'}
    common.write_json(out / 'result.json', report)
    print(json.dumps(report, indent=2) if args.json else report['status'])
    return {'pass': 0, 'fail': 1}.get(report['status'], 3)
