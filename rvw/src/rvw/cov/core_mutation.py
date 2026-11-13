"""Serial, resumable mutation campaigns over project-declared exported RTL.

Adapters are trusted project code. Build errors cannot supply detection evidence.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import time

from rvw.common.proc import run_group

SCHEMA = 'rvw.core-mutation/1'
KILLS = ('killed by self-check', 'killed by reference mismatch',
         'killed by generated check or property')
STATES = (*KILLS, 'survived', 'equivalent (proved)', 'timeout', 'invalid')


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def mutant_set_identity(plan):
    return sha256(json.dumps([plan['rtl_sha256'],plan['mutants']],sort_keys=True).encode()).hexdigest()


def write(path, data):
    temp = path.with_suffix('.new')
    temp.write_text(json.dumps(data, indent=2) + '\n')
    temp.replace(path)


def candidates(text, scopes, limit):
    """Single operator changes, restricted to declared modules and line patterns.

    No comments or strings supply mutation sites. The plan records exact old/new
    lines so each generated candidate can be audited before a native run.
    """
    swaps = {'==': '!=', '!=': '==', '<<': '>>', '>>': '<<',
             '+': '-', '-': '+', '&': '|', '|': '&', '^': '|', '<': '>', '>': '<'}
    token = re.compile(r'===|!==|>>>|<<<|==|!=|<<|>>|&&|\|\||[+\-&|^<>]')
    rows = []
    module = None
    block = False
    for number, line in enumerate(text.splitlines(keepends=True), 1):
        # Preserve offsets while removing comments and string literals.
        masked = list(line)
        i = 0
        while i < len(line):
            if block:
                masked[i] = ' '
                if line[i:i+2] == '*/':
                    masked[i:i+2] = '  '; i += 2; block = False
                else: i += 1
            elif line[i:i+2] == '/*':
                masked[i:i+2] = '  '; i += 2; block = True
            elif line[i:i+2] == '//':
                masked[i:] = ' ' * (len(line)-i); break
            elif line[i] == '"':
                masked[i] = ' '; i += 1
                while i < len(line):
                    char = line[i]; masked[i] = ' '; i += 1
                    if char == '\\' and i < len(line): masked[i] = ' '; i += 1
                    elif char == '"': break
            else: i += 1
        code = ''.join(masked)
        match = re.search(r'\bmodule\s+(\w+)', code)
        if match: module = match[1]
        for scope in scopes:
            if module != scope['module'] or not re.search(scope['pattern'], code): continue
            for match in token.finditer(code):
                op = match.group()
                # Never alter nonblocking assignments or declarations.
                if op not in swaps or (op == '<' and code[match.end():].startswith('=')): continue
                new = line[:match.start()] + swaps[op] + line[match.end():]
                rows.append(dict(id=f'm{len(rows)+1:04d}', module=module, scope=scope['id'],
                                 line=number, old=line, new=new, operator=op))
                break
            break
        if re.search(r'\bendmodule\b', code): module = None
    # Round robin avoids spending the complete budget on the first module.
    groups = [[r for r in rows if r['scope'] == s['id']] for s in scopes]
    selected = []
    while any(groups) and len(selected) < limit:
        for group in groups:
            if group and len(selected) < limit: selected.append(group.pop(0))
    return selected


def prepare(manifest, out, count=60):
    manifest = Path(manifest).resolve()
    data = json.loads(manifest.read_text())
    if data.get('schema') != 'rvw.core-mutation-project/1': raise ValueError('invalid project schema')
    if count < 1: raise ValueError('count must be positive')
    root = manifest.parent
    source = (root / data['rtl']).resolve()
    inputs = {str((root / p).resolve()): digest(root / p) for p in data['inputs']}
    inputs[str(source)] = digest(source)
    inputs[str(manifest)] = digest(manifest)
    for test in data['tests']:
        if str((root / test['elf']).resolve()) not in inputs:
            raise ValueError('declare each ELF in inputs')
    scopes = data['scopes']
    if not scopes or len({s['id'] for s in scopes}) != len(scopes): raise ValueError('unique scopes required')
    if any(not re.fullmatch(r'[A-Za-z0-9_-]+', t['id']) for t in data['tests']):
        raise ValueError('test IDs must be simple names')
    if not data['tests'] or len({t['id'] for t in data['tests']}) != len(data['tests']):
        raise ValueError('unique tests required')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(source, out / 'original.v')
    plan = dict(schema=SCHEMA, project=data, root=str(root), inputs=inputs,
                rtl_sha256=digest(source), mutants=candidates(source.read_text(), scopes, count))
    if not plan['mutants']: raise ValueError('no mutation sites in declared scope')
    write(out / 'plan.json', plan)
    return plan


def classify(receipt, returncode):
    """Require explicit test evidence; generic FAIL/exit 1 never earns a kill."""
    if receipt.get('schema') != 'rvw.mutation-test/1': return 'invalid'
    state = receipt.get('outcome')
    if state in KILLS:
        if not receipt.get('evidence'): return 'invalid'
        return state
    if state == 'pass' and returncode == 0 and receipt.get('strict_spike_match') is True:
        return 'pass'
    if state == 'timeout': return 'timeout'
    return 'invalid'


def _command(argv, values, root, log, deadline):
    remaining = deadline-time.monotonic()
    if remaining <= 0: return None
    command = [str(word).format_map(values) for word in argv]
    with log.open('w') as stream:
        return run_group(['nice', '-n', '15', *command], cwd=root,
                         env=dict(os.environ, RVW_VEX_LOCK='vex-mutate', RVW_SBT_LOCK='sbt-mutate'),
                         timeout=remaining, stdout=stream, stderr=stream)


def run_campaign(work_dir, budget_s=120, resume=False):
    if budget_s <= 0: raise ValueError('budget must be positive')
    out = Path(work_dir).resolve()
    plan = json.loads((out / 'plan.json').read_text())
    for path, expected in plan['inputs'].items():
        if digest(path) != expected: raise ValueError('input changed: '+path)
    if digest(out/'original.v') != plan['rtl_sha256']: raise ValueError('original RTL changed')
    plan_hash = digest(out/'plan.json')
    mutant_set_hash=mutant_set_identity(plan)
    state_file = out/'results.json'
    if state_file.exists():
        if not resume: raise ValueError('results exist; use resume')
        state = json.loads(state_file.read_text())
        if state['plan_sha256'] != plan_hash: raise ValueError('plan changed')
    else: state = dict(schema=SCHEMA, plan_sha256=plan_hash, baseline=None, mutants=[])
    state['mutant_set_sha256']=mutant_set_hash
    deadline = time.monotonic()+budget_s
    project = plan['project']; root = plan['root']
    build = out/'build'
    build.mkdir(exist_ok=True)
    rtl = out/'candidate.v'
    values = dict(rtl=str(rtl), original=str(out/'original.v'), build=str(build), out=str(out))
    done = {r['id'] for r in state['mutants'] if r['state'] != 'timeout'}
    control = dict(id='baseline', module='control', scope='control')
    work = ([] if state['baseline'] and state['baseline']['state']=='survived' else [control])
    work += [m for m in plan['mutants'] if m['id'] not in done]
    try:
        for mutant in work:
            if time.monotonic() >= deadline: break
            text = (out/'original.v').read_text()
            if mutant['id'] != 'baseline':
                lines = text.splitlines(keepends=True)
                if lines[mutant['line']-1] != mutant['old']: raise ValueError('mutant line changed')
                lines[mutant['line']-1] = mutant['new']; text = ''.join(lines)
            rtl.write_text(text)
            row = dict(id=mutant['id'], scope=mutant['scope'], module=mutant['module'],
                       rtl_sha256=digest(rtl), tests=[], state='invalid', first_killer=None)
            folder = out/mutant['id']; folder.mkdir(exist_ok=True)
            result = _command(project['build'], values, root, folder/'build.log', deadline)
            if result is None or result.timed_out: row['state']='timeout'
            elif result.returncode: row['reason']='build or elaboration failed'
            else:
                row['state']='survived'
                for test in project['tests']:
                    receipt_path = folder/(test['id']+'.json')
                    receipt_path.unlink(missing_ok=True)
                    v = dict(values, receipt=str(receipt_path), elf=str((Path(root)/test['elf']).resolve()),
                             test=test['id'], rtl_sha256=row['rtl_sha256'])
                    execution = _command(project['test'], v, root, folder/(test['id']+'.log'), deadline)
                    if execution is None or execution.timed_out: outcome='timeout'; receipt={}
                    else:
                        try: receipt=json.loads(receipt_path.read_text())
                        except (OSError, ValueError): receipt={}
                        outcome = classify(receipt, execution.returncode)
                        if receipt.get('rtl_sha256') != row['rtl_sha256'] or receipt.get('test') != test['id']:
                            outcome='invalid'
                    row['tests'].append(dict(id=test['id'], source=test['source'], tier=test['tier'],
                                             outcome=outcome, receipt=receipt))
                    if outcome != 'pass':
                        row['state']=outcome
                        if outcome in KILLS: row['first_killer']=test['id']
                        break
                if row['state']=='survived' and mutant['id'] != 'baseline':
                    # Use the existing formal equivalence command. A timeout or a
                    # bounded/conditional result never proves equivalence.
                    proof = folder/'equivalence'
                    if proof.exists(): shutil.rmtree(proof)
                    v = dict(values, proof=str(proof))
                    result = _command(project['equivalence'], v, root, folder/'equivalence.log', deadline)
                    try: evidence=json.loads((proof/'result.json').read_text())
                    except (OSError, ValueError): evidence={}
                    row['equivalence']=evidence
                    if (result is not None and not result.timed_out and result.returncode==0
                            and evidence.get('schema')=='rvw.formal.equiv/1'
                            and evidence.get('status')=='equivalent'):
                        row['state']='equivalent (proved)'
                    row['test_gap'] = (result is not None and not result.timed_out
                                       and result.returncode==1
                                       and evidence.get('schema')=='rvw.formal.equiv/1'
                                       and evidence.get('status')=='not_equivalent')
            if mutant['id']=='baseline': state['baseline']=row
            else:
                state['mutants']=[r for r in state['mutants'] if r['id']!=row['id']]+[row]
            write(state_file,state)
            if mutant['id']=='baseline' and row['state']!='survived': break
    finally:
        # One build directory serves all mutants. Never retain native build trees.
        shutil.rmtree(build)
    state['pending']=len(plan['mutants'])-len(state['mutants'])
    state['status']='complete' if (not state['pending'] and state['baseline'] and state['baseline']['state']=='survived'
                                  and not any(r['state']=='timeout' for r in state['mutants'])) else 'inconclusive'
    state['counts']={s:sum(r['state']==s for r in state['mutants']) for s in STATES}
    state['tables']=tables(state['mutants'])
    write(state_file,state)
    return state


def tables(rows):
    modules = {}; sources = {}
    timing=dict(property_before_reference=0,property_timing_unmeasured=0,reference_first_kills=0)
    for row in rows:
        counts = modules.setdefault(row['scope'],dict(total=0, killed=0, invalid=0, timeout=0, equivalent=0))
        counts['total']+=1
        counts['killed']+=row['state'] in KILLS
        counts['invalid']+=row['state']=='invalid'
        counts['timeout']+=row['state']=='timeout'
        counts['equivalent']+=row['state']=='equivalent (proved)'
        if row['state']==KILLS[1]: timing['reference_first_kills']+=1
        for test in row['tests']:
            entry=sources.setdefault(test['source'],dict(run=0,first_kills=0))
            entry['run']+=1; entry['first_kills']+=test['outcome'] in KILLS
            if test['outcome']==KILLS[2]:
                evidence=test.get('receipt',{}).get('evidence',{})
                detected=evidence.get('detection_cycle') if isinstance(evidence,dict) else None
                mismatch=evidence.get('reference_mismatch_cycle') if isinstance(evidence,dict) else None
                if type(detected) is int and type(mismatch) is int and 0<=detected<mismatch:
                    timing['property_before_reference']+=1
                else: timing['property_timing_unmeasured']+=1
    for counts in modules.values():
        denominator=counts['total']-counts['invalid']-counts['timeout']-counts['equivalent']
        counts['eligible']=denominator
        counts['kill_rate']=counts['killed']/denominator if denominator else None
    return dict(modules=modules,sources=sources,timing=timing)
