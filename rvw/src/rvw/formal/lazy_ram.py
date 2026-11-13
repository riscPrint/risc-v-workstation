"""Lazy word-state abstraction after Yosys's formal memory lowering."""
import copy
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import time
from rvw.common.proc import run_group
from .portfolio import race


def abstract_words(design, top, words, watched):
    result = copy.deepcopy(design)
    module = result['modules'][top]
    used = set()
    for word in words.values():
        bits = module['netnames'][word]['bits']
        if any(type(b) is not int for b in bits) or len(set(bits)) != len(bits) or used & set(bits):
            raise ValueError('mapped memory words must have distinct nonconstant state bits')
        used.update(bits)
    for index, word in words.items():
        if index in watched:
            continue
        bits = module['netnames'][word]['bits']
        drivers = [n for n, c in module['cells'].items()
                   if c['type'].startswith(('$dff', '$ff')) and c['connections'].get('Q') == bits]
        if len(drivers) != 1 or any(type(b) is not int for b in bits):
            raise ValueError('mapped memory word needs one whole-word flip-flop driver')
        name = f'rvw_ram_word_{index}'
        if name in module['ports'] or name in module['netnames']:
            raise ValueError('RAM abstraction port collision')
        del module['cells'][drivers[0]]
        module['ports'][name] = {'direction': 'input', 'bits': bits}
        # An abstract input can vary at every step. Do not retain source init
        # attributes on any aliases of the freed word bits.
        for net in module['netnames'].values():
            if set(net['bits']) & set(bits):
                net.get('attributes', {}).pop('init', None)
    return result


def observed_addresses(directory, names):
    values = set()
    for trace in directory.rglob('trace*.vcd'):
        codes = set()
        for line in trace.read_text().splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[0] == '$var' and parts[4].lstrip('\\') in names:
                codes.add(parts[3])
            elif len(parts) == 2 and parts[0].startswith('b') and parts[1] in codes:
                bits = parts[0][1:]
                if bits and set(bits) <= {'0', '1'}:
                    values.add(int(bits, 2))
            elif len(parts) == 1 and parts[0][:1] in ('0', '1') and parts[0][1:] in codes:
                values.add(int(parts[0][0]))
    return values


def run(plan, root, out, *, timeout=10, budget=60):
    if any(not math.isfinite(v) or v <= 0 for v in (timeout, budget)):
        raise ValueError('timeout and budget must be finite and positive')
    top, memory = plan['top'], plan['memory']
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', top):
        raise ValueError('invalid top')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    inputs, source_hashes = [], []
    for i, source in enumerate(plan['sources']):
        data = (Path(root) / source['path']).read_bytes()
        if sha256(data).hexdigest() != source['sha256'] or source.get('format', 'verilog') != 'verilog':
            raise ValueError('RAM sources must be hash-pinned Verilog')
        if b'`include' in data or b'$readmem' in data:
            raise ValueError('RAM sources must be self-contained')
        p = out / f'input{i}.sv'
        p.write_bytes(data)
        inputs.append(p.name)
        source_hashes.append(source['sha256'])
    deadline = time.monotonic() + budget
    def yosys(script, log):
        left = deadline - time.monotonic()
        if left <= 0:
            raise ValueError('RAM preparation budget exhausted')
        r = run_group(['yosys', '-Q', '-T', '-p', script], cwd=out, capture=True, timeout=min(timeout, left))
        (out / log).write_text((r.stdout or '') + (r.stderr or ''))
        if r.timed_out or r.returncode:
            raise ValueError('RAM lowering failed; see ' + log)
    yosys('read -formal ' + ' '.join(inputs) + '; prep -top ' + top + '; flatten; memory_collect; write_json collected.json; memory_map -formal; opt_clean; write_json mapped.json', 'prepare.log')
    collected = json.loads((out / 'collected.json').read_text())['modules'][top]
    if memory not in collected['cells'] or collected['cells'][memory]['type'] != '$mem_v2':
        raise ValueError('memory must name a collected memory cell')
    cell = collected['cells'][memory]
    params = cell['parameters']
    size, width, offset = (int(params[k], 2) for k in ('SIZE', 'WIDTH', 'OFFSET'))
    if offset >= 2**31:
        raise ValueError('negative memory offsets are not supported')
    limit = plan.get('max_words', 64)
    if type(limit) is not int or not 1 <= size <= limit <= 4096:
        raise ValueError('memory size exceeds max_words (maximum 4096)')
    name = params['MEMID'].lstrip('\\')
    words = {i: f'{name}[{i}]' for i in range(offset, offset + size)}
    design = json.loads((out / 'mapped.json').read_text())
    if any(w not in design['modules'][top]['netnames'] for w in words.values()):
        raise ValueError('formal lowering did not retain every memory word name')
    address_names, constant_addresses = set(), set()
    abits = int(params['ABITS'], 2)
    for start in range(0, len(cell['connections']['RD_ADDR']), abits):
        bits = cell['connections']['RD_ADDR'][start:start + abits]
        if all(b in ('0', '1') for b in bits):
            constant_addresses.add(sum(int(b) << i for i, b in enumerate(bits)))
        for net, body in collected['netnames'].items():
            if body['bits'] == bits:
                address_names.add(net.split('.')[-1].lstrip('\\'))
    watched, rows = set(), []
    status, proof_kind, stop = 'inconclusive', 'none', 'budget_exhausted'
    for n in range(size + 1):
        if deadline - time.monotonic() <= 0:
            break
        model = abstract_words(design, top, words, watched)
        p = out / f'round-{n}.json'
        p.write_text(json.dumps(model))
        source = out / f'round-{n}.sv'
        yosys(f'read_json {p.name}; write_verilog {source.name}', f'round-{n}-export.log')
        left = deadline - time.monotonic()
        if left <= 0:
            break
        case = {'top': top, 'mode': 'prove', 'depth': plan.get('depth', 20),
                'engines': plan.get('engines', ['abc:pdr']),
                'sources': [{'path': source.name, 'sha256': sha256(source.read_bytes()).hexdigest()}]}
        directory = out / f'round-{n}'
        r = race(case, out, directory, timeout=min(timeout, left / 2))
        row = {'watched': sorted(watched), 'memory_state_bits': width * len(watched),
               'status': r['status'], 'result': directory.name + '/result.json'}
        rows.append(row)
        if r['status'] == 'pass':
            status, proof_kind, stop = 'pass', 'unbounded_memory_overapproximation', 'proved'
            break
        if r['status'] == 'fail' and len(watched) == size:
            status, proof_kind, stop = 'fail', 'counterexample', 'concrete_counterexample'
            break
        if r['status'] != 'fail':
            stop = 'engine_inconclusive'
            break
        row['status'] = 'inconclusive'
        row['reason'] = 'abstract_counterexample'
        addresses = (constant_addresses | observed_addresses(directory, address_names)) & (words.keys() - watched)
        chosen = min(addresses) if addresses else min(words.keys() - watched)
        row['restored_address'] = chosen
        watched.add(chosen)
    return {'schema': 'rvw.formal-lazy-ram/1', 'status': status, 'proof_kind': proof_kind,
            'memory': memory, 'words': size, 'word_width': width, 'original_memory_state_bits': size * width,
            'watched': sorted(watched), 'rounds': rows, 'stop_reason': stop,
            'source_sha256': source_hashes,
            'limits': 'Yosys memory_map -formal preserves source memory behavior. Unwatched word state becomes '
                      'unconstrained per-step input. Abstract failures only request refinement. '
                      'Address samples prioritize restoration; missing samples fall back to the next word. '
                      'No source environment assumption is discharged.'}
