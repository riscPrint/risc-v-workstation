"""Solver cores for one frozen SMT query, with explicit design bindings."""
from hashlib import sha256
from pathlib import Path
import json
import re
import time

from rvw.common.capture import Capture
from rvw.common.proc import run_group
from . import common


def expressions(text):
    """Split SMT-LIB forms without interpreting strings, quoted symbols or comments."""
    tokens = re.findall(r';[^\n]*|"(?:[^"]|"")*"|\|[^|]*\||[()]|[^\s();]+', text)
    stack, forms = [], []
    for token in tokens:
        if token.startswith(';'):
            continue
        if token == '(':
            stack.append([])
        elif token == ')':
            if not stack:
                raise ValueError('unbalanced SMT-LIB')
            form = stack.pop()
            (stack[-1] if stack else forms).append(form)
        elif stack:
            stack[-1].append(token)
        else:
            raise ValueError('expected SMT-LIB form')
    if stack:
        raise ValueError('unbalanced SMT-LIB')
    return forms


def render(form):
    return '(' + ' '.join(render(x) if isinstance(x, list) else x for x in form) + ')'


def prepare(text):
    background, assertions = [], {}
    allowed = {'set-logic', 'declare-fun', 'declare-const', 'declare-sort', 'define-sort',
               'define-fun', 'define-fun-rec', 'define-funs-rec', 'declare-datatype', 'declare-datatypes'}
    for form in expressions(text):
        if form[0] in {'check-sat', 'get-unsat-core', 'get-model', 'exit', 'set-option', 'set-info'}:
            continue
        if form[0] == 'assert':
            if len(form) != 2:
                raise ValueError('malformed assertion')
            term = form[1]
            if not isinstance(term, list) or len(term) != 4 or term[0] != '!' or term[2] != ':named':
                raise ValueError('each assertion needs (! TERM :named LABEL) for design mapping')
            label = term[3]
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', label) or label in assertions:
                raise ValueError('assertion labels must be unique plain identifiers')
            assertions[label] = render(form)
        elif form[0] in allowed:
            background.append(render(form))
        else:
            raise ValueError('unsupported SMT command: ' + str(form[0]))
    if not assertions:
        raise ValueError('no named assertions')
    return background, assertions


def extract(background, assertions, solve):
    """Deletion-minimal core. Unknown removal checks retain their constraints."""
    status, core = solve(background, assertions)
    if status != 'unsat':
        return {'status': 'inconclusive', 'solver_status': status, 'labels': [], 'minimal': False}
    if not core or not set(core) <= assertions.keys():
        raise ValueError('solver returned missing or unknown core labels')
    kept = {name: assertions[name] for name in core}
    complete = True
    for name in list(kept):
        trial = {k: v for k, v in kept.items() if k != name}
        verdict, _ = solve(background, trial)
        if verdict == 'unsat':
            kept = trial
        elif verdict != 'sat':
            complete = False
    return {'status': 'pass', 'solver_status': 'unsat', 'labels': sorted(kept),
            'minimal': complete, 'minimality': 'deletion minimal, not minimum cardinality'}


def run(args):
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    capture = Capture(out / 'inputs')
    exported = None
    if getattr(args, "result", None):
        if getattr(args, "cell_level", False):
            from .cell_model import export
        else:
            from .core_model import export
        args.smt2, args.mapping, exported = export(args.result, out, capture, args.timeout, getattr(args, "depth", None), getattr(args, "property", None))
    if not args.smt2 or not args.mapping:
        raise ValueError("provide --result or both --smt2 and --mapping")
    source = capture.file(Path(args.smt2)).copy
    bindings = json.loads(capture.file(Path(args.mapping)).copy.read_text())
    if bindings.get('schema') != 'rvw.smt-bindings/1' or not bindings.get('property_id'):
        raise ValueError('expected rvw.smt-bindings/1 with property_id')
    background, assertions = prepare(source.read_text())
    if set(assertions) != set(bindings['constraints']):
        raise ValueError('mapping must bind every named constraint exactly once')
    tool = capture.tool(args.solver, identity_only=True)
    deadline, calls = time.monotonic() + args.timeout, []
    def solve(base, selected):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return 'timeout', []
        query = out / f'query-{len(calls)}.smt2'
        query.write_text('(set-option :produce-unsat-cores true)\n' + '\n'.join(
            [*base, *selected.values(), '(check-sat)', '(get-unsat-core)']) + '\n')
        result = run_group([str(tool.path), '-smt2', str(query)], capture=True, timeout=remaining)
        stdout = result.stdout or ''
        (out / f'{query.stem}.log').write_text(stdout + (result.stderr or ''))
        lines = stdout.strip().splitlines()
        status = lines[0].strip() if lines else 'error'
        # Z3 exits nonzero for get-unsat-core after SAT. SAT itself remains valid evidence.
        if status not in {'sat', 'unsat', 'unknown'} or (status == 'unsat' and result.returncode != 0):
            status = 'error'
        core = re.findall(r'[A-Za-z_][A-Za-z0-9_]*', '\n'.join(lines[1:])) if status == 'unsat' else []
        calls.append({'query': query.name, 'status': status, 'exit_code': result.returncode})
        return status, core
    feasibility = None
    if exported:
        feasibility, conflict = solve(background, {k: v for k, v in assertions.items() if k != "failure"})
    if feasibility is not None and feasibility != "sat":
        environment = extract(background, {k: v for k, v in assertions.items() if k != "failure"}, solve) if feasibility == "unsat" else None
        report = {"status": "inconclusive", "solver_status": feasibility, "labels": [],
                  "minimal": False, "reason": "bounded environment is not shown feasible",
                  "environment_core": environment["labels"] if environment else conflict,
                  "environment_minimal": environment["minimal"] if environment else False}
    else:
        report = extract(background, assertions, solve)
    report.update(schema='rvw.solver-core/1', property_id=bindings['property_id'],
                  requirement_ids=bindings.get('requirement_ids', []),
                  query_sha256=sha256(source.read_bytes()).hexdigest(), calls=calls,
                  constraints={k: bindings['constraints'][k] for k in report['labels']},
                  scope='One SMT query. Not an unbounded RTL proof or a coverage exclusion.')
    if exported:
        selected = set(report.get('environment_core', report['labels']))
        report['assumptions'] = [dict(binding, label=label, in_core=(label in selected if report["status"] == "pass" or "environment_core" in report and report["solver_status"] == "unsat" else None))
            for label, binding in bindings['constraints'].items() if binding.get('kind') == 'assumption']
        report['property_activation'] = []
        for guard in exported.get('activation_queries', []):
            status = 'not_checked'
            blocking = None
            if feasibility == 'sat':
                selected = {k: v for k, v in assertions.items() if k != 'failure'}
                selected['activation'] = '(assert (! ' + guard['term'] + ' :named activation))'
                status, _ = solve(background, selected)
                if status == 'unsat':
                    blocking = extract(background, selected, solve)
            report['property_activation'].append(dict(property_id=guard['property_id'],
                status={'sat': 'reached', 'unsat': 'not_reached_bounded'}.get(status, 'inconclusive'),
                solver_status=status, depth=exported['depth'], scope=guard['scope'],
                blocking_core=blocking, blocking_assumptions=[bindings['constraints'][label] for label in blocking['labels']
                    if label in bindings['constraints'] and bindings['constraints'][label].get('kind') == 'assumption'] if blocking else []))
        report['bounded_model'] = {'top': exported['top'], 'depth': exported['depth'], 'feasibility': feasibility,
            'scope': 'Aggregate bounded assertion query from captured SBY RTLIL, including AIGER engine runs. Core units are mapped cell equations with --cell-level; otherwise sample constraints. No exclusion authority.'}
    if exported and exported.get('vacuity_queries'):
        report['logical_vacuity'] = []
        for probe in exported['vacuity_queries']:
            statuses = []
            if feasibility == 'sat' and report['solver_status'] == 'unsat':
                for term in probe['replacements']:
                    selected = {k:v for k,v in assertions.items() if k != 'failure'}
                    selected['replacement_failure'] = '(assert (! '+term+' :named replacement_failure))'
                    status, _ = solve(background, selected)
                    statuses.append(status)
            report['logical_vacuity'].append(dict(property_id=probe['property_id'], atom_bit=probe['atom_bit'],
                status='replacement_vacuous_bounded' if statuses == ['unsat','unsat'] else 'sensitive_bounded' if 'sat' in statuses else 'inconclusive',
                replacements=statuses, scope='Combinational assertion-leaf substitution at every bounded sample. No temporal or unbounded non-vacuity claim.'))
    if exported and 'logic' in exported:
        labels = report['labels'] if report['status'] == 'pass' else []
        used = {bindings['constraints'][k].get('cell_id') for k in labels}
        report['cell_coverage'] = {'scope': exported['coverage_scope'], 'logic': exported['logic'],
            'core_cells': sorted(used - {None}), 'outside_core': [c['id'] for c in exported['logic'] if c['id'] not in used],
            'status': 'bounded_core' if report['status'] == 'pass' else 'inconclusive'}
    if args.db:
        from rvw.query.db import DesignDB, QueryError
        db = DesignDB(args.db, capture=capture)
        try:
            report['design'] = []
            for label, binding in report['constraints'].items():
                for signal in binding.get('signals', []):
                    try:
                        location = db.signal_json(db.resolve_one(signal))
                    except QueryError as exc:
                        location = {'status': 'unresolved', 'error': str(exc)}
                    report['design'].append({'label': label, 'signal': signal, 'location': location})
            report['database_staleness'] = db.staleness()
        finally:
            db.close()
    capture.verify_tools()
    report['input_capture'] = capture.record()
    common.write_json(out / 'result.json', report)
    print(json.dumps(report, indent=2) if args.json else report['status'])
    return 0 if report['status'] == 'pass' else 1
