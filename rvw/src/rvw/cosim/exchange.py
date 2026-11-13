"""RVVI-TEXT 0.5 and Spike commit-log exchange with explicit loss accounting."""
import io
import json
import re
import shlex
from pathlib import Path
from .trace import Trace

SPEC = 'https://github.com/riscv-verification/RVVI/blob/04dc469012f718ffe104c1c1d0cd8cea66f96724/RVVI-TEXT/README.md'


def _state(value):
    # STATE has a quoted string value. A JSON string safely quotes JSON payloads.
    return 'STATE "rvw.c2" ' + json.dumps(json.dumps(value, separators=(',', ':')))


def export(records, kind):
    """Export complete C2 with a lossless, optional vendor state extension."""
    header, *rows = records
    # Validate before publishing. Keep original bytes/fields for round trips.
    trace = Trace(io.StringIO(''.join(json.dumps(r)+'\n' for r in records)))
    try:
        list(trace)
    finally:
        trace.close()
    if kind == 'rvvi':
        lines = ['VERSION 0 5', f'PARAMS 2 XLEN {header["xlen"]} NHART {len(header.get("harts", [0]))}', _state(header)]
        cycle = 0
        for r in rows:
            delta = r['cycle'] - cycle
            cycle = r['cycle']
            prefix = f'CYCLE {delta} HART {r.get("hart", 0)} '
            if 'event' not in r:
                prefix += f'ORDER {r["order"]} ' + ('TRAP' if r['trap'] else 'RET') + f' {r["pc"]} {r["insn"]} MODE {hex(r["mode"])} '
                if r['rd']:
                    prefix += f'X {r["rd"]} {r["rd_wdata"]} '
            elif r['event'] == 'irq':
                prefix += f'NET "rvw.irq_levels" {r["levels"]} '
            lines.append(prefix + _state(r))
        return '\n'.join(lines)+'\n'
    if kind == 'spike':
        lines = ['# RVW-C2 ' + json.dumps(header)]
        for r in rows:
            if 'event' not in r:
                if r['trap']:
                    raise ValueError('Spike commit logs cannot represent a faulting retirement; use RVVI')
                line = f'core {r.get("hart", 0):3d}: {r["mode"]} {r["pc"]} ({r["insn"]})'
                if r['rd']:
                    line += f' x{r["rd"]:2d} {r["rd_wdata"]}'
                lines.append(line)
            lines.append('# RVW-C2 ' + json.dumps(r))
        return '\n'.join(lines)+'\n'
    raise ValueError('unsupported export format')


def import_stream(text, kind):
    """Return complete C2 if vendor state is present, else sparse observations."""
    restored, observations = [], []
    if kind == 'rvvi':
        lines = text.splitlines()
        if not lines or lines[0].strip() != 'VERSION 0 5':
            raise ValueError('expected RVVI-TEXT VERSION 0 5')
        cycle, hart, parameters, orders = 0, 0, {}, {}
        for line in lines[1:]:
            tokens = shlex.split(line)
            if 'PARAMS' in tokens:
                pos = tokens.index('PARAMS')
                count = int(tokens[pos+1])
                pairs = tokens[pos+2:pos+2+2*count]
                if count < 0 or len(pairs) != 2*count:
                    raise ValueError('invalid RVVI parameter count')
                parameters.update(zip(pairs[::2], pairs[1::2]))
            if 'CYCLE' in tokens:
                delta = int(tokens[tokens.index('CYCLE')+1])
                if delta < 0:
                    raise ValueError('negative RVVI cycle delta')
                cycle += delta
            if 'HART' in tokens:
                hart = int(tokens[tokens.index('HART')+1])
            if 'ORDER' in tokens:
                orders[hart] = int(tokens[tokens.index('ORDER')+1])
            if 'STATE' not in tokens:
                if 'RET' in tokens or 'TRAP' in tokens:
                    key = 'RET' if 'RET' in tokens else 'TRAP'
                    at = tokens.index(key)
                    observations.append(dict(pc=tokens[at+1], insn=tokens[at+2], trap=key == 'TRAP', raw_elements=tokens))
                continue
            at = tokens.index('STATE')
            if tokens[at+1] != 'rvw.c2' or at+3 != len(tokens):
                raise ValueError('unsupported RVVI state extension')
            obj = json.loads(tokens[at+2])
            if 'cycle' in obj and (obj['cycle'] != cycle or obj.get('hart', 0) != hart):
                raise ValueError('RVVI cycle/hart conflicts with C2 state')
            if obj.get('event') == 'irq' and 'NET' in tokens:
                pos = tokens.index('NET')
                if tokens[pos+1] != 'rvw.irq_levels' or int(tokens[pos+2], 0) != int(obj['levels'], 16):
                    raise ValueError('RVVI net conflicts with C2 state')
            if 'order' in obj and not ('RET' in tokens or 'TRAP' in tokens):
                raise ValueError('RVVI retirement missing for C2 state')
            if 'RET' in tokens or 'TRAP' in tokens:
                key = 'RET' if 'RET' in tokens else 'TRAP'
                pos = tokens.index(key)
                if int(obj['order']) != orders.get(hart, 0):
                    raise ValueError('RVVI order conflicts with C2 state')
                orders[hart] = int(obj['order']) + 1
                if 'MODE' in tokens and int(tokens[tokens.index('MODE')+1], 0) != obj['mode']:
                    raise ValueError('RVVI mode conflicts with C2 state')
                if (int(tokens[pos+1], 0), int(tokens[pos+2], 0), key == 'TRAP') != (int(obj['pc'], 16), int(obj['insn'], 16), obj['trap']):
                    raise ValueError('RVVI fields conflict with C2 state')
                if 'X' in tokens:
                    pos = tokens.index('X')
                    if (int(tokens[pos+1]), int(tokens[pos+2], 0)) != (obj['rd'], int(obj['rd_wdata'], 16)):
                        raise ValueError('RVVI write conflicts with C2 state')
            restored.append(obj)
    elif kind == 'spike':
        pattern = re.compile(r'core\s+(\d+):\s+([013])\s+(0x[0-9a-f]+)\s+\((0x[0-9a-f]+)\)(.*)')
        for line in text.splitlines():
            if line.startswith('# RVW-C2 '):
                restored.append(json.loads(line[len('# RVW-C2 '):]))
            elif line.startswith('core'):
                match = pattern.fullmatch(line)
                if not match:
                    raise ValueError('unsupported Spike commit-log line')
                hart, mode, pc, insn, writes = match.groups()
                item = dict(hart=int(hart), mode=int(mode), pc=pc, insn=insn)
                write = re.fullmatch(r'\s+x\s*(\d+)\s+(0x[0-9a-f]+)\s*', writes) if writes else None
                if writes and not write:
                    raise ValueError('unsupported Spike effect; no fields were discarded')
                if write:
                    item.update(rd=int(write[1]), rd_wdata=write[2])
                observations.append(item)
            elif line.strip() and not line.startswith('#'):
                raise ValueError('unsupported Spike log content')
    else:
        raise ValueError('unsupported import format')
    if restored:
        trace = Trace(io.StringIO(''.join(json.dumps(r)+'\n' for r in restored)))
        try:
            list(trace)
        finally:
            trace.close()
        if kind == 'spike':
            rows = [r for r in restored[1:] if 'event' not in r]
            if len(rows) != len(observations) or any(any(o[k] != r[k] for k in ('mode', 'pc', 'insn')) or o.get('rd', 0) != r['rd'] or (r['rd'] and o['rd_wdata'] != r['rd_wdata']) for o, r in zip(observations, rows)):
                raise ValueError('Spike fields conflict with C2 state')
        if kind == 'rvvi':
            if observations:
                raise ValueError('mixed RVVI state and sparse retirements')
            expected = {'XLEN': restored[0]['xlen'], 'NHART': len(restored[0].get('harts', [0]))}
            if any(name in parameters and int(parameters[name], 0) != value for name, value in expected.items()):
                raise ValueError('RVVI parameters conflict with C2 state')
        return restored, []
    if not observations:
        raise ValueError('no observations')
    return [], observations


def convert(source, out, source_format, target_format):
    text = Path(source).read_text()
    if source_format == 'c2':
        records, sparse = [json.loads(line) for line in text.splitlines()], []
    else:
        records, sparse = import_stream(text, source_format)
    if sparse:
        if target_format != 'observations':
            raise ValueError('sparse input lacks C2 fields; choose observations output')
        result = dict(schema='rvw.observations/1', source_format=source_format,
                      observations=sparse, scope='only fields present; no architectural check',
                      missing=['pc_next', 'sources', 'memory', 'asynchronous_events', 'end_status'])
        output = json.dumps(result)+'\n'
    elif target_format == 'c2':
        output = ''.join(json.dumps(r)+'\n' for r in records)
    else:
        output = export(records, target_format)
    with Path(out).open('x') as stream:
        stream.write(output)
    return dict(schema='rvw.cosim-exchange/1', status='converted', out=str(out),
                independent_check=False, sparse=bool(sparse))
