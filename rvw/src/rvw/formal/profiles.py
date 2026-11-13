"""Pinned RVA23/RVB23 named-extension obligations and scoped proof evidence."""
import hashlib
import json
import os
from pathlib import Path
import re


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def extract(path, digest):
    raw = Path(path).read_bytes()
    if sha(raw) != digest:
        raise ValueError('profile document SHA-256 mismatch')
    lines = raw.decode().splitlines()
    records, profile, category = [], None, None
    for i, line in enumerate(lines):
        heading = re.fullmatch(r'=== (RV[AB]23[US]64) Profile', line)
        if heading:
            profile, category = heading[1], None
        elif line.startswith('=== '):
            profile, category = None, None
        if not profile:
            continue
        if line.startswith('==== '):
            category = 'mandatory' if 'Mandatory Extensions' in line else 'optional' if 'Optional Extensions' in line else None
            continue
        bullet = re.match(r'- \*([A-Za-z][A-Za-z0-9]*)\* ', line)
        if category and bullet:
            from .profile_clauses import bullet_end
            end = bullet_end(lines,i)
            text = '\n'.join(lines[i:end])
            records.append(dict(id=profile + '.' + bullet[1].lower(), profile=profile,
                                extension=bullet[1].lower(), requirement=category, text=text,
                                obligation_sha256=sha(text.encode()),
                                source=dict(path=str(Path(path).resolve()), sha256=digest, line=i+1)))
    if not records:
        raise ValueError('no supported named profile obligations found')
    from .profile_clauses import additional
    return sorted(records+additional(Path(path),digest,lines),key=lambda row:row['source']['line'])


def proof_evidence(entry, obligation, root):
    path = root / os.path.expandvars(entry['result'])
    raw = path.read_bytes()
    if sha(raw) != entry['sha256'] or entry['obligation_sha256'] != obligation['obligation_sha256']:
        return dict(status='unverified', reason='proof or obligation hash mismatch')
    result = json.loads(raw)
    valid = (result.get('status') == 'pass' and result.get('proof_kind') == 'unbounded'
             and type(result.get('assertions')) is int and result['assertions'] > 0
             and (result.get('reachability') or {}).get('status') == 'reachable')
    return dict(status='verified' if valid else 'unverified', result=str(path.resolve()),
                sha256=sha(raw), restrictions=result.get('restrictions', []),
                scope='reviewed obligation-to-property mapping; captured proof environment')


def assess(manifest):
    from rvw.cov.isa import load_manifest, extensions, check_manifest
    path = Path(manifest).resolve()
    plan = json.loads(path.read_text())
    if plan.get('schema') != 'rvw.profile-plan/1':
        raise ValueError('expected rvw.profile-plan/1')
    declarations=plan.get('declarations',{})
    if not isinstance(declarations,dict) or any(type(value) is not bool for value in declarations.values()):
        raise ValueError('declarations must map clause IDs to Boolean values')
    isa_path = path.parent / os.path.expandvars(plan['isa_manifest'])
    isa = load_manifest(isa_path)
    xlen, implemented = extensions(isa['isa'])
    rows = []
    for document in plan['documents']:
        imported = extract(path.parent / os.path.expandvars(document['path']), document['sha256'])
        for row in imported:
            row['source'].update({k: document[k] for k in ('revision', 'url') if k in document})
        rows += imported
    from .profile_clauses import expand_sha, active as obligation_active, declared
    rows = expand_sha(rows,implemented)
    selected = plan['profiles']
    available = {r['profile'] for r in rows}
    if not selected or set(selected) - available:
        raise ValueError('selected profile absent from pinned documents')
    seen, reports = set(), {}
    for profile in selected:
        active = [r.copy() for r in rows if r['profile'] == profile]
        # Supervisor profiles explicitly inherit the unprivileged extension set.
        if 'S64' in profile:
            user = profile.replace('S64','U64')
            if user not in available:
                raise ValueError('supervisor obligations need the user-profile document')
            existing = {r['extension']: r for r in active}
            for row in rows:
                if row['profile'] == user and row['extension'] in existing and row['requirement'] == 'mandatory':
                    existing[row['extension']]['requirement'] = 'mandatory'
                if row['profile'] == user and row['extension'] not in existing:
                    inherited = dict(row, id=profile + '.' + row['extension'], profile=profile, inherited_from=user)
                    active.append(inherited)
        result_rows = []
        for row in active:
            if row['id'] in seen:
                raise ValueError('duplicate profile obligation')
            seen.add(row['id'])
            required = obligation_active(row,implemented)
            row['active'] = required
            if not required:
                row['status'] = 'not_selected'
            elif row['id'] in plan.get('unsupported', []) or row['extension'] in plan.get('unsupported', []):
                row['status'] = 'unsupported'
            elif not declared(row,implemented,xlen,plan):
                row['status'] = 'missing'
            else:
                row['status'] = 'implemented'
                entry = plan.get('proofs', {}).get(row['id'])
                if entry:
                    try:
                        row['evidence'] = proof_evidence(entry, row, path.parent)
                    except (OSError, ValueError, KeyError) as exc:
                        row['evidence'] = dict(status='unverified', reason=str(exc))
                    if row['evidence']['status'] == 'verified':
                        row['status'] = 'verified'
            row['checkers'] = plan.get('checkers', {}).get(row['id'], [])
            row['tests'] = []
            for test in plan.get('tests', {}).get(row['id'], []):
                test_path = path.parent / test
                row['tests'].append(dict(path=test, present=test_path.is_file(),
                                         sha256=sha(test_path.read_bytes()) if test_path.is_file() else None))
            row['missing_tests'] = [t['path'] for t in row['tests'] if not t['present']]
            if required and not row['tests']:
                row['missing_tests'] = ['no tests declared']
            result_rows.append(row)
        reports[profile] = dict(obligations=result_rows,
                                **{s:[r['id'] for r in result_rows if r['status']==s]
                                   for s in ('implemented','verified','missing','unsupported','not_selected')})
    return dict(schema='rvw.profile-report/1', status='inconclusive', profiles=reports,
                isa_configuration=check_manifest(isa_path), manifest_sha256=sha(path.read_bytes()),
                limits=['Captured extension, mandatory-base and recognized conditional clauses. Recommendations are not requirements.',
                        'Optional extensions activate when selected in the ISA manifest. Base and standalone clauses require explicit project declarations.',
                        'Attached notes remain part of each obligation. Parameter conditions still need reviewed property mappings.',
                        'Normative conditions within each captured requirement remain part of its reviewed proof obligation.',
                        'Implemented means declared in project data. Verified means a hash-bound mapped unbounded proof with reachability.',
                        'No full profile compliance or design acceptance verdict.'])


def compare(before, after):
    old = {r['id']:r for p in before['profiles'].values() for r in p['obligations']}
    new = {r['id']:r for p in after['profiles'].values() for r in p['obligations']}
    changes = []
    for key in sorted(old.keys() | new.keys()):
        a, b = old.get(key), new.get(key)
        if a is None or b is None or any(a.get(k) != b.get(k) for k in ('obligation_sha256','requirement','active','kind','when_any','parent_extension','checkers')):
            changes.append(dict(id=key, kind='added' if a is None else 'removed' if b is None else 'changed',
                                before=a, after=b, affected_checkers=(b or a)['checkers']))
    return dict(changes=changes, requires_explicit_adoption=bool(changes),
                missing_tests={r['id']:r['missing_tests'] for r in new.values() if r['active'] and r['missing_tests']},
                limits='Text/selection obligation diff. Test-file presence is not execution. No pin or model is changed.')


def main(args):
    try:
        result = assess(args.manifest)
        if getattr(args, 'baseline', None):
            result['specification_diff'] = compare(assess(args.baseline), result)
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=False)
        from .profile_clauses import catalogs,source_index
        (out/'index.json').write_text(json.dumps(source_index(result),indent=2)+'\n')
        directory=out/'catalogs'
        directory.mkdir()
        generated=catalogs(result)
        for digest,catalog in generated.items():
            (directory/(digest+'.json')).write_text(json.dumps(catalog,indent=2)+'\n')
        result['artifacts']={'index':'index.json','catalogs':['catalogs/'+digest+'.json' for digest in generated]}
        result['unmapped_checkers']=sorted({key for catalog in generated.values() for key in catalog['unmapped_checkers']})
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result) if args.json else result['status'])
        return 3
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps(dict(status='error', error=str(exc))))
        return 2
