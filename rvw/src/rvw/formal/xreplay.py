"""Native four-state replay of solver input sequences on captured source RTL.

No solver state is loaded. Registers and memories retain their RTL initialization.
A replay that does not reproduce X is inconclusive, never a design pass.
"""
import re
import io

from . import common, vcdsnap
from .common import vid


def vectors(path, inputs, masks=None):
    """Read complete solver steps. Preserve X/Z and refuse missing input bits."""
    text = path.read_text()
    # SMTBMC adds unscoped step/event metadata. Remove only those declared codes.
    metadata = re.findall(r'^\$var (?:integer|event) \d+ (\S+) smt_(?:step|clock) \$end$', text, re.M)
    text = re.sub(r'^\$var (?:integer|event) \d+ \S+ smt_(?:step|clock) \$end\n', '', text, flags=re.M)
    for code in metadata:
        text = re.sub(r'^(?:[01xz]' + re.escape(code) + r'|b[01xz]+ ' + re.escape(code) + r')\n', '', text, flags=re.M)
    # The terminal timestamp contains metadata only. Never invent an extra DUT cycle.
    chunks = re.split(r'^#(\d+)\n', text, flags=re.M)
    times = [int(chunks[i]) for i in range(1, len(chunks), 2)
             if chunks[i+1].strip() and int(chunks[i]) % 10 == 0]
    rows = []
    for time in times:
        snap = vcdsnap.take_stream(io.StringIO(text), 'rvw_xprop_top', None, None, time)
        values = {'.'.join(v.path): (v, snap.values.get(v.code)) for v in snap.vars}
        row = {}
        for p in inputs:
            if p.name not in values or values[p.name][1] is None:
                raise ValueError('counterexample lacks input ' + p.name)
            value = values[p.name][1].removeprefix('b').lower()
            pad = value[0] if value[0] in 'xz' else '0'
            value = value.rjust(p.width, pad)
            if masks and p.name in masks:
                mask = values.get(masks[p.name])
                if mask is None or mask[1] is None:
                    raise ValueError('counterexample lacks unknown mask for ' + p.name)
                bits = mask[1].removeprefix('b').rjust(p.width, '0')
                if set(bits) - {'0', '1'}:
                    raise ValueError('unknown encoding mask')
                if any(x == '0' and b not in '01' for x,b in zip(bits,value)):
                    raise ValueError('missing defined counterexample input bits')
                value = ''.join('x' if x == '1' else b for x,b in zip(bits,value))
            elif set(value) - {'0', '1'}:
                raise ValueError('undefined counterexample input in defined-input campaign')
            row[p.name] = value
        rows.append(row)
    if not rows:
        raise ValueError('counterexample has no complete steps')
    return rows


def replay(args, out, ports, labels, result, reset, ties, R, S, comb):
    info = result['replay'] = {'backend': 'icarus', 'model': 'captured-source-rtl',
                               'status': 'inconclusive', 'traces': []}
    if not result['x_reaches']:
        info['reason'] = 'no formal candidates'
        return
    inputs = [p for p in ports if p.direction == 'input' and p.name not in ties
              and (comb or p.name not in (args.clock, reset))]
    confirmed = set()
    for index, trace in enumerate(result['traces']):
        entry = {'trace': trace, 'status': 'inconclusive'}
        info['traces'].append(entry)
        try:
            rows = vectors(out / trace, inputs, {p.name: f'rvw_input_x{i}' for i,p in enumerate(ports)
                           if p in inputs} if args.x_inputs else None)
        except (ValueError, SystemExit) as exc:
            entry['reason'] = str(exc)
            continue
        lines = ['module replay_top;']
        conns = []
        for p in ports:
            if p.direction == 'input':
                lines.append('reg ' + p.decl() + ';')
                conns.append(f'.{vid(p.name)}({vid(p.name)})')
        observed = sorted({t['signal'] for t in labels} | {t['when_valid'] for t in labels if t['when_valid']})
        widths = {p.name:p.width for p in common.ports_from_json(out / 'exposed_ports.json', args.top)}
        for i, name in enumerate(observed):
            if name in {p.name for p in ports if p.direction == 'input'}:
                continue
            path = '.'.join(vid(part) for part in name.split('.'))
            lines.append(f'wire [{widths[name]-1}:0] obs{i} = dut.{path};')
        def ref(name):
            return vid(name) if name in {p.name for p in ports if p.direction == 'input'} else f'obs{observed.index(name)}'
        lines += [f'{args.top} dut({", ".join(conns)});', 'initial begin']
        for name, (width, value) in ties.items():
            lines.append(f"{vid(name)} = {width}'d{value};")
        if not comb:
            lines.append(f'{vid(args.clock)} = 0;')
        for step, row in enumerate(rows):
            for p in inputs:
                lines.append(f"{vid(p.name)} = {p.width}'b{row[p.name]};")
            if reset:
                on = int(args.reset_active == 'high')
                lines.append(f"{vid(reset)} = 1'b{on if step < R else 1-on};")
            lines.append('#1;')
            if comb or step > R + S:
                for t in labels:
                    cond = f"({ref(t['when_valid'])} === 1'b1) && " if t['when_valid'] else ''
                    lines.append(f'if ({cond}(^{ref(t["signal"])} === 1\'bx)) '
                                 f'$display("RVW_X {t["assert"]} {step} %b", {ref(t["signal"])});')
            if not comb:
                lines += [f'{vid(args.clock)} = 1;', '#1;', f'{vid(args.clock)} = 0;']
        lines += ['$display("RVW_DONE");', '$finish;', 'end', 'endmodule']
        bench = out / f'replay-{index}.sv'
        bench.write_text('\n'.join(lines) + '\n')
        args._input_snapshot.seal(bench)
        log = out / f'replay-{index}.log'
        rc, _ = common.run(['iverilog', '-g2012', '-DSYNTHESIS', '-s', 'replay_top', '-o', f'replay-{index}.vvp',
                            *map(str, args._input_snapshot.sources), bench.name], out, out / f'replay-{index}-compile.log', args.timeout)
        if rc:
            entry['reason'] = 'Icarus compile failed'
            continue
        rc, _ = common.run(['vvp', f'replay-{index}.vvp'], out, log, args.timeout)
        output = log.read_text()
        entry['log'] = log.name
        if rc or 'RVW_DONE' not in output:
            entry['reason'] = 'Icarus replay incomplete'
            continue
        hits = re.findall(r'^RVW_X (rvw_x_\d+) (\d+) ([01xz]+)$', output, re.M)
        entry.update(status='complete', unknowns=[{'assert': a, 'step': int(s), 'bits': b} for a,s,b in hits])
        confirmed.update(a for a, _, _ in hits)
    for target in result['inventory']:
        if target['assert'] in confirmed:
            target.update(disposition='confirmed', backend='icarus', reason='4-state replay observed X/Z at target')
        elif target['disposition'] == 'candidate':
            target.update(disposition='inconclusive', reason='4-state replay did not confirm this candidate')
    info['status'] = 'confirmed' if confirmed else 'inconclusive'
