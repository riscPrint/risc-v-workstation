"""Export ABC PDR candidates and reuse certified, cone-matched RTL predicates.

Helpers remain assertions in every target job. A cache never supplies a verdict.
"""
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import shutil

from rvw.common.proc import run_group
from .lemma_cone import identity, digest
from .portfolio import race

IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')


def expression(lemma):
    terms = []
    for item in lemma['literals']:
        name, bit, value = item['signal'], item['bit'], item['value']
        if not IDENT.fullmatch(name) or type(bit) is not int or bit < 0 or type(value) is not int or value not in (0, 1):
            raise ValueError('invalid mapped lemma literal')
        terms.append(f"({name}[{bit}] == 1'b{value})")
    if not terms:
        raise ValueError('empty lemma cube')
    return '!(' + ' && '.join(terms) + ')'


def candidates(pla, aim):
    mapping = {}
    for line in aim.splitlines():
        fields = line.split()
        if len(fields) == 4 and fields[0] == 'latch' and IDENT.fullmatch(fields[3]):
            mapping[int(fields[1])] = (fields[3], int(fields[2]))
    columns, width, cubes, declared = None, None, [], None
    ended = False
    for line in pla.splitlines():
        fields = line.split()
        if not fields or line.startswith('#'):
            continue
        if fields[0] == '.i':
            width = int(fields[1])
        elif fields[0] == '.ilb':
            if any(not re.fullmatch(r'lo[0-9]+', name) for name in fields[1:]):
                raise ValueError('unsupported PDR invariant columns')
            columns = [int(name[2:]) for name in fields[1:]]
        elif fields[0] == '.p':
            declared = int(fields[1])
        elif fields[0] == '.o':
            if fields[1:] != ['1']:
                raise ValueError('expected one invariant output')
        elif fields[0] == '.ob':
            continue
        elif fields[0] == '.e':
            ended = True
        elif fields[0].startswith('.') or ended or len(fields) != 2 or fields[1] != '1' or not re.fullmatch('[01-]+', fields[0]):
            raise ValueError('unsupported PDR invariant PLA')
        else:
            cubes.append(fields[0])
    if not ended or width is None or columns is None or len(columns) != width or declared != len(cubes) or any(len(c) != width for c in cubes):
        raise ValueError('incomplete PDR invariant PLA')
    result, skipped = [], 0
    for cube in cubes:
        used = [(mapping.get(col), int(value)) for col, value in zip(columns, cube) if value != '-']
        if not used or any(binding is None for binding, _ in used):
            skipped += 1  # Auxiliary SBY state and unmapped or inverted latches are not RTL predicates.
            continue
        literals = sorted([{'signal': binding[0], 'bit': binding[1], 'value': value} for binding, value in used],
                          key=lambda item: (item['signal'], item['bit']))
        lemma = {'id': digest(literals), 'literals': literals}
        lemma['expression'] = expression(lemma)
        result.append(lemma)
    return result, skipped


def prepare(plan, root, out, timeout):
    if not IDENT.fullmatch(plan['top']):
        raise ValueError('invalid top module')
    sources = []
    for i, item in enumerate(plan['sources']):
        if item.get('format', 'verilog') != 'verilog':
            raise ValueError('lemma libraries require self-contained Verilog')
        data = (Path(root) / item['path']).read_bytes()
        if sha256(data).hexdigest() != item['sha256']:
            raise ValueError('source hash mismatch')
        if b'`include' in data or b'$readmem' in data:
            raise ValueError('lemma libraries require self-contained memory and sources')
        path = out / f'input{i}.sv'
        path.write_bytes(data)
        sources.append(path)
    if not sources:
        raise ValueError('no RTL sources')
    script = 'read -formal ' + ' '.join(json.dumps(str(p)) for p in sources)
    script += '; prep -flatten -top ' + plan['top']
    script += '; write_json design.json; chformal -remove; write_verilog -noattr base.v'
    r = run_group(['yosys', '-Q', '-T', '-p', script], cwd=out, capture=True, timeout=timeout)
    (out / 'prepare.log').write_text((r.stdout or '') + (r.stderr or ''))
    if r.timed_out or r.returncode or not (out / 'design.json').exists():
        return None
    return json.loads((out / 'design.json').read_text())['modules'][plan['top']]


def child_plan(source, top, engines):
    return {'top': top, 'sources': [{'path': str(source), 'sha256': sha256(source.read_bytes()).hexdigest()}],
            'engines': engines, 'mode': 'prove'}


def inject(base, lemmas):
    before, separator, after = base.rpartition('endmodule')
    if not separator or after.strip():
        raise ValueError('expected one flattened top module')
    return before + '\n' + '\n'.join('always @* assert(' + expression(row) + ');' for row in lemmas) + '\nendmodule\n'


def run(plan, root, out, *, library=None, timeout=15):
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('timeout must be finite and positive')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out / 'manifest.json').write_text(json.dumps(plan, indent=2) + '\n')
    report = {'schema': 'rvw.formal-ic3-lemmas/1', 'status': 'inconclusive', 'proof_kind': 'none',
              'mode': 'reuse' if library is not None else 'export', 'entries': [], 'rejected': [],
              'source_sha256': [s['sha256'] for s in plan['sources']],
              'limits': 'PDR cubes are candidates until a fresh independent unbounded proof certifies them. '
                        'Only matching complete transition cones select cached predicates. '
                        'Helpers remain assertions and the target always needs a fresh native proof. '
                        'No source assumptions, speedup or whole-block qualification is implied.'}
    if not shutil.which('yosys'):
        return {**report, 'reason': 'not_installed'}
    module = prepare(plan, root, out, timeout)
    if module is None:
        return {**report, 'reason': 'preparation_failed'}
    if not any(c['type'] == '$assert' or (c['type'] == '$check' and c.get('parameters', {}).get('FLAVOR') == 'assert')
               for c in module['cells'].values()):
        return {**report, 'reason': 'no_checks'}
    if any(c['type'] == '$assume' or (c['type'] == '$check' and c.get('parameters', {}).get('FLAVOR') == 'assume')
           for c in module['cells'].values()):
        return {**report, 'reason': 'source_assumptions_unsupported'}
    if library is None:
        native = race({**plan, 'engines': ['abc:pdr'], 'mode': 'prove'}, root, out / 'discovery',
                      timeout=timeout, abc_invariants=True)
        report['discovery'] = native
        if native['status'] != 'pass':
            report['status'] = 'fail' if native['status'] == 'fail' else 'inconclusive'
            return {**report, 'reason': 'discovery_' + native['status']}
        plas = list((out / 'discovery').rglob('invariants.pla'))
        if len(plas) != 1:
            return {**report, 'reason': 'no_invariant_export'}
        aim = plas[0].parent.parent / 'model/design_aiger.aim'
        entries, report['unmapped_cubes'] = candidates(plas[0].read_text(), aim.read_text())
        report['export_sha256'] = {'pla': sha256(plas[0].read_bytes()).hexdigest(), 'aim': sha256(aim.read_bytes()).hexdigest()}
    else:
        raw = Path(library).read_bytes()
        cached = json.loads(raw)
        if cached.get('schema') != 'rvw.formal-lemma-library/1':
            raise ValueError('expected rvw.formal-lemma-library/1')
        (out / 'input-library.json').write_bytes(raw)
        report['library_sha256'] = sha256(raw).hexdigest()
        entries = cached['entries']
    selected = []
    for row in entries:
        try:
            expression(row)
            cone, _ = identity(module, [(p['signal'], p['bit']) for p in row['literals']])
            if library is not None and (row.get('certification') != 'fresh_unbounded' or cone != row['cone_sha256']):
                raise ValueError('cone_or_certification_mismatch')
            selected.append({**row, 'cone_sha256': cone})
        except ValueError as exc:
            report['rejected'].append({'id': row['id'], 'reason': str(exc)})
    if library is None:
        if not selected:
            return {**report, 'reason': 'no_mapped_candidates'}
        helper = out / 'helpers.sv'
        helper.write_text(inject((out / 'base.v').read_text(), selected))
        proof = race(child_plan(helper, plan['top'], ['abc:pdr']), out, out / 'certification', timeout=timeout)
        report['certification'] = proof
        if proof['status'] != 'pass':
            return {**report, 'reason': 'candidate_certification_' + proof['status']}
        selected = [{**row, 'certification': 'fresh_unbounded'} for row in selected]
        report.update(status='pass', proof_kind='unbounded_candidate_certification', entries=selected)
        cache = {'schema': 'rvw.formal-lemma-library/1', 'entries': selected,
                 'source_sha256': report['source_sha256'], 'export_sha256': report['export_sha256'],
                 'certification_result': 'certification/result.json'}
        (out / 'library.json').write_text(json.dumps(cache, indent=2) + '\n')
    else:
        # Keep original assertions. Helpers are additional assertions, never assumptions.
        files = sorted(out.glob('input*.sv'))
        script = 'read -formal ' + ' '.join(json.dumps(str(p)) for p in files)
        script += '; prep -flatten -top ' + plan['top'] + '; write_verilog -noattr target.v'
        r = run_group(['yosys', '-Q', '-T', '-p', script], cwd=out, capture=True, timeout=timeout)
        (out / 'target-prepare.log').write_text((r.stdout or '') + (r.stderr or ''))
        if r.timed_out or r.returncode:
            return {**report, 'reason': 'target_preparation_failed'}
        target = out / 'strengthened.sv'
        target.write_text(inject((out / 'target.v').read_text(), selected))
        proof = race(child_plan(target, plan['top'], plan.get('engines', ['smtbmc:yices'])), out,
                     out / 'target', timeout=timeout)
        report.update(entries=selected, target=proof, status=proof['status'],
                      proof_kind='fresh_unbounded_with_helpers' if proof['status'] == 'pass' else 'none')
        # A failed helper can come from a foreign or damaged library. Do not label it a DUT bug.
        if selected and proof['status'] == 'fail':
            report.update(status='inconclusive', proof_kind='none', reason='helper_or_target_failed')
    return report
