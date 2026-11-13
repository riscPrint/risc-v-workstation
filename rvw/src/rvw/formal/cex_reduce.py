"""Counterexample reduction with an exact-property replay oracle."""
from pathlib import Path
from rvw.wave import vcd


def reduce_trace(source, target, ports, scope, reproduces, max_checks=100):
    """Keep the first values; remove later input events only after replay accepts."""
    if max_checks < 1:
        raise ValueError('max_checks must be positive')
    with open(source) as stream:
        header = vcd.read_header(stream)
        records = [(t, c, r) for t, c, r in vcd.body_records(stream) if c is not None]
    inputs = {scope + '.' + p['name'] for p in ports if p['direction'] == 'input'}
    codes = {v.code for v in header.vars if v.name in inputs}
    # The replay still contains the complete header and internal trace values. Only DUT
    # input changes drive the replay; the replay engine computes all internal values again.
    first = {}
    for i, (_, code, _) in enumerate(records):
        first.setdefault(code, i)
    times = sorted({t for t, _, _ in records})
    checks, removed = [], []
    def write(rows):
        with open(target, 'w') as output:
            output.writelines(header.lines)
            last = None
            for t, code, raw in rows:
                if t != last:
                    output.write(f'#{t}\n')
                    last = t
                vcd.write_value(output, raw, code)
    def test(rows, action):
        write(rows)
        ok = reproduces(Path(target), len(checks)) is True
        checks.append({'action': action, 'same_failure': ok})
        return ok
    if not test(records, 'baseline'):
        raise ValueError('reduction baseline does not reproduce the same property under assumptions')
    # Test every shorter prefix in time order. Nonmonotone failure observations are allowed.
    end = times[-1]
    prefix_complete = True
    for time in times[:-1]:
        if len(checks) >= max_checks:
            prefix_complete = False
            break
        trial = [r for r in records if r[0] <= time]
        if test(trial, f'prefix@{time}'):
            records, end = trial, time
            break
    # Deleting changes is a greedy reduction, not a global minimum stimulus.
    candidates = [(i, r) for i, r in enumerate(records) if r[1] in codes and first[r[1]] != i]
    for _, record in reversed(candidates):
        if len(checks) >= max_checks:
            break
        trial = list(records)
        trial.remove(record)
        if test(trial, f'remove:{record[1]}@{record[0]}'):
            records = trial
            removed.append({'time': record[0], 'code': record[1]})
    write(records)
    return {'schema': 'rvw.cex-reduction/1', 'status': 'reproduced', 'end_time': end,
            'earliest_prefix_checked': prefix_complete, 'removed_input_events': removed,
            'checks': checks, 'wave': str(target),
            'limits': 'Greedy input-event reduction. Assumptions and initial values remain. Not a global minimum or proof.'}


def testbench(source, target, ports, top):
    """Portable event stimulus for Icarus (-g2012) or Verilator (--binary --timing)."""
    from .common import check_ident
    check_ident('top', top)
    with open(source) as stream:
        header = vcd.read_header(stream)
        records = list(vcd.body_records(stream))
    variables = {v.name: v for v in header.vars}
    codes, lines = {}, [f'`timescale {header.timescale}/1ps', 'module rvw_replay_tb;']
    # A VCD time unit must be representable in Verilog. Sub-picosecond traces use 1fs precision.
    lines[0] = f'`timescale {header.timescale}/1fs'
    for port in ports:
        name = check_ident('port', port['name'])
        if port['direction'] not in ('input', 'output'):
            raise ValueError('replay testbench does not support inout ports')
        var = variables.get(top + '.' + name)
        width = len(port['bits'])
        kind = 'reg' if port['direction'] == 'input' else 'wire'
        lines.append(f'{kind} [{width-1}:0] {name};')
        if port['direction'] == 'input':
            if var is None or var.width != width:
                raise ValueError('trace input is missing or has the wrong width: ' + name)
            codes[var.code] = (name, width)
    lines += [f'{top} dut(' + ', '.join(f'.{p["name"]}({p["name"]})' for p in ports) + ');',
              'initial begin', '$dumpfile("replay.vcd"); $dumpvars(0, rvw_replay_tb);']
    previous = 0
    for time, code, raw in records:
        if code not in codes:
            continue
        name, width = codes[code]
        if time > previous:
            lines.append(f'#{time-previous};')
            previous = time
        bits = raw[1:] if raw.startswith('b') else raw
        if not bits or any(c not in '01xXzZ' for c in bits):
            raise ValueError('unsupported trace value')
        lines.append(f"{name} = {width}'b{bits};")
    finish = max((r[0] for r in records), default=previous)
    lines += [f'#{finish - previous + 1}; $finish;', 'end', 'endmodule']
    Path(target).write_text('\n'.join(lines) + '\n')
