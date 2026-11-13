"""Checked finite state-encoding relations, never state equality assumptions."""
import hashlib
import json

from . import common


def load(path, out):
    raw = common.check_path('--state-encoding', path).read_bytes()
    (out/'state-encoding.json').write_bytes(raw)
    spec = json.loads(raw)
    rows = spec.get('mappings')
    if spec.get('schema') != 'rvw.equiv-encoding/1' or not isinstance(rows, list) or not 1 <= len(rows) <= 64:
        raise ValueError('state encoding needs rvw.equiv-encoding/1 and 1..64 mappings')
    used = {'gold': set(), 'gate': set()}
    for row in rows:
        if set(row) != {'gold', 'gate', 'values'}:
            raise ValueError('encoding mapping needs gold, gate and values')
        for side in used:
            name = row[side]
            common.check_hier('encoding register', name)
            if name in used[side]:
                raise ValueError('encoding registers must be distinct on each side')
            used[side].add(name)
        values = row['values']
        if not isinstance(values, list) or not 1 <= len(values) <= 256:
            raise ValueError('encoding mapping needs 1..256 value pairs')
        if any(not isinstance(pair, list) or len(pair) != 2 or any(type(v) is not int or v < 0 for v in pair) for pair in values):
            raise ValueError('encoding values must be unsigned integer pairs')
        if any(len({pair[index] for pair in values}) != len(values) for index in (0, 1)):
            raise ValueError('encoding values must be one-to-one')
    return rows, {'path':'state-encoding.json', 'sha256':hashlib.sha256(raw).hexdigest(),
                  'rule':'closed output and finite encoding relations; no state assumptions'}


def expose(rows, side, design, states, top, directory, budget, snapshot):
    """Add observation-only ports to the captured, flattened module."""
    module = design['modules'][top]
    index = 0 if side == 'gold' else 1
    for number, row in enumerate(rows):
        name = row[side]
        if name not in states:
            raise ValueError('encoding name must identify an inventoried register: '+name)
        bits = states[name]
        if any(pair[index] >= 1 << len(bits) for pair in row['values']):
            raise ValueError('encoding value does not fit register: '+name)
        port = f'rvw_encoding_raw{number}'
        if port in module['ports'] or port in module['netnames']:
            raise ValueError('encoding observation port collision')
        module['ports'][port] = {'direction':'output', 'bits':list(bits)}
        module['netnames'][port] = {'hide_name':0, 'bits':list(bits), 'attributes':{}}
    source = directory/'encoding.json'
    model = directory/'encoding.il'
    script = directory/'encoding.ys'
    source.write_text(json.dumps(design)+'\n')
    script.write_text(f'read_json {source}\nwrite_rtlil {model}\n')
    rc, _ = common.run(['yosys','-Q','-s',str(script)], directory, directory/'encoding.log', budget())
    if rc:
        raise ValueError('encoding observation export failed')
    for path in (source, model, script):
        snapshot.seal(path)
    return model


def harness(rows, side, states):
    declarations, connections, statements = [], [], []
    index = 0 if side == 'gold' else 1
    for number, row in enumerate(rows):
        width = len(states[row[side]])
        code_width = max(1, (len(row['values'])-1).bit_length())
        raw = f'rvw_encoding_raw{number}'
        code = f'rvw_encoding_code{number}'
        valid = f'rvw_encoding_valid{number}'
        declarations += [f'output [{code_width-1}:0] {code}',
                         f'output {valid}_gold', f'output {valid}_gate']
        connections.append(f'.{raw}({raw})')
        statements.append(f'wire [{width-1}:0] {raw};')
        conditions = [f'({raw} == {width}\'d{pair[index]})' for pair in row['values']]
        decoded = f'{code_width}\'d0'
        for ordinal, condition in reversed(list(enumerate(conditions))):
            decoded = f'{condition} ? {code_width}\'d{ordinal} : ({decoded})'
        statements += [f'assign {code} = rvw_ready ? ({decoded}) : {code_width}\'d0;',
            f'assign {valid}_{side} = !rvw_ready || ({" || ".join(conditions)});',
            f'assign {valid}_{"gate" if side == "gold" else "gold"} = 1\'b1;']
    return declarations, connections, statements


def observations(rows):
    return [f'rvw_encoding_{suffix}{number}{side}' for number in range(len(rows))
            for suffix, side in (('code',''), ('valid','_gold'), ('valid','_gate'))]


def audit(rows, bodies, pairs, missing):
    for row in rows:
        pairs[:] = [p for p in pairs if p['gold'] != row['gold'] and p['gate'] != row['gate']]
    # Recompute after removing any name/leaf pair displaced by an encoding row.
    for side, states in zip(('gold','gate'), bodies):
        covered = {p[side] for p in pairs} | {row[side] for row in rows}
        missing[side] = sorted(set(states)-covered)
    pairs.extend({'gold':row['gold'], 'gate':row['gate'], 'method':'encoding',
                  'gold_width':len(bodies[0][row['gold']]), 'gate_width':len(bodies[1][row['gate']]),
                  'values':row['values']} for row in rows)
