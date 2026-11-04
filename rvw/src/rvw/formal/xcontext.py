"""Native X observations in the parent design, from reset and explicit input ties."""
import json
import re
import time

from . import common
from .common import vid


def run(args):
    from .flows import _inputs, _ties, _remaining
    out = common.begin(args)
    started = time.time()
    if args.timeout is None or args.timeout <= 0:
        common.die('x-context requires a positive --timeout')
    if args.reset_cycles < 1 or args.depth <= args.reset_cycles:
        common.die('depth must exceed positive reset cycles')
    if not args.signal or any(not common.is_hier(s) for s in args.signal):
        common.die('provide valid hierarchical --signal targets')
    snapshot, ports, _ = _inputs(args, out, ['SYNTHESIS'])
    reset = common.resolve_reset(args, ports)
    names = {p.name: p for p in ports}
    if not reset or args.clock not in names or names[args.clock].width != 1 or names[args.clock].direction != 'input':
        common.die('x-context requires a reset and a one-bit clock')
    ties = _ties(args, ports, {args.clock, reset})
    missing = [p.name for p in ports if p.direction == 'input'
               and p.name not in ties and p.name not in (args.clock, reset)]
    if missing or any(p.direction == 'inout' for p in ports):
        common.die('tie every non-clock/reset input; missing: ' + ', '.join(missing))
    lines = ['module context_top;']
    for p in ports:
        if p.direction == 'input':
            lines.append('reg ' + p.decl() + ';')
    conns = [f'.{vid(p.name)}({vid(p.name)})' for p in ports if p.direction == 'input']
    lines += [f'{args.top} dut({", ".join(conns)});', 'initial begin']
    lines.append(f'{vid(args.clock)} = 0;')
    for name, (width, value) in ties.items():
        lines.append(f"{vid(name)} = {width}'d{value};")
    for step in range(args.depth):
        active = int(args.reset_active == 'high')
        lines.append(f"{vid(reset)} = 1'b{active if step < args.reset_cycles else 1-active};")
        lines.append('#5;')
        if step >= args.reset_cycles:
            for index, signal in enumerate(args.signal):
                path = '.'.join(vid(s) for s in signal.split('.'))
                lines.append(f'$display("RVW_CONTEXT {index} {step} %b", dut.{path});')
        lines += [f'{vid(args.clock)} = 1;', '#5;', f'{vid(args.clock)} = 0;']
    lines += ['$display("RVW_CONTEXT_DONE");', '$finish;', 'end', 'endmodule']
    bench = out / 'context.sv'
    bench.write_text('\n'.join(lines) + '\n')
    snapshot.seal(bench)
    result = {'schema': 'rvw.formal.x-context/1', 'top': args.top, 'status': 'inconclusive',
              'backend': 'icarus', 'depth': args.depth, 'reset_cycles': args.reset_cycles,
              'clock': args.clock, 'reset': reset, 'reset_active': args.reset_active,
              'ties': {k:v for k, (_,v) in ties.items()},
              'restrictions': ['constant input environment', 'native RTL initialization; no state injection',
                               'no X observation does not prove unreachability',
                               'observations are unconditional; payload validity is not checked'],
              'inventory': [{'signal': s, 'disposition': 'inconclusive', 'observations': []}
                            for s in args.signal]}
    rc, _ = common.run(['iverilog', '-g2012', '-DSYNTHESIS', '-s', 'context_top',
                        '-o', 'context.vvp', *map(str, snapshot.sources), bench.name],
                       out, out / 'compile.log', _remaining(args.timeout, started))
    if rc:
        result['reason'] = 'Icarus compile failed or timed out'
    else:
        rc, _ = common.run(['vvp', 'context.vvp'], out, out / 'context.log',
                           _remaining(args.timeout, started))
        output = (out / 'context.log').read_text()
        hits = re.findall(r'^RVW_CONTEXT (\d+) (\d+) ([01xz]+)$', output, re.M)
        complete = rc == 0 and 'RVW_CONTEXT_DONE' in output
        for index, target in enumerate(result['inventory']):
            samples = [(int(step), bits) for i, step, bits in hits if int(i) == index]
            # Require every requested observation, including known values.
            if complete and len(samples) == args.depth - args.reset_cycles:
                target['observations'] = [{'step': s, 'bits': b} for s,b in samples if set(b) & set('xz')]
                if target['observations']:
                    target['disposition'] = 'reachable-in-core'
                else:
                    target['reason'] = 'no X/Z in this bounded input environment; unreachability not proved'
            else:
                target['reason'] = 'native replay incomplete'
    snapshot.finish(result)
    if result['input_snapshot']['problems']:
        for target in result['inventory']:
            target['disposition'] = 'inconclusive'
            target['reason'] = 'input capture verification failed'
    common.write_json(out / 'result.json', result)
    print(json.dumps(result, indent=2) if args.json else f"x-context: {out / 'result.json'}")
    return 1
