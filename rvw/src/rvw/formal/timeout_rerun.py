"""Replay retained timeout jobs: python -m rvw.formal.timeout_rerun PLAN --out OUT."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import time

from rvw.common.proc import run_group
from rvw.formal.common import sigterm_raises
from rvw.formal.portfolio import ENGINES, installed, parse_status
from rvw.formal.runtime import load_average


def seconds(value):
    match = re.fullmatch(r'(\d+(?:\.\d+)?)([smh]?)', value)
    if not match:
        raise ValueError('time limit must be a positive number with optional s, m or h')
    result = float(match[1]) * {'':1, 's':1, 'm':60, 'h':3600}[match[2]]
    if not math.isfinite(result) or result <= 0:
        raise ValueError('time limit must be finite and positive')
    return result


def timed_out_checks(report):
    """Select aggregate timeout checks; a losing engine timeout is not a retry."""
    found = set()
    def visit(value):
        if isinstance(value, list):
            for child in value:
                visit(child)
        elif isinstance(value, dict):
            name = value.get('check', value.get('id'))
            attempts = value.get('engines', value.get('rows', []))
            statuses = {r.get('status') for r in attempts if isinstance(r, dict)} if isinstance(attempts, list) else set()
            reason = str(value.get('reason', value.get('inconclusive', ''))).lower()
            status = value.get('status')
            activation = value.get('instruction_activation') or {}
            if name and activation.get('status') == 'timeout':
                found.add(name+'-activation')
            if name:
                for attempt in value.get('native_attempts', []):
                    if attempt.get('status') == 'timeout':
                        found.add(name+':'+attempt['task'])
            if name and not value.get('conditional_native_proof') and status not in ('pass','proven','bounded','fail','failed'):
                if status == 'timeout' or value.get('native_status')=='timeout' or 'timeout' in reason or 'timed out' in reason or (
                    'timeout' in statuses and not statuses & {'pass','bounded_pass','fail'}):
                    found.add(name)
            for key, child in value.items():
                if key not in ('engines','settings','check_options'):
                    visit(child)
    visit(report)
    return sorted(found)


def freeze(source, directory, engines, text=None):
    """Keep options, scripts and embedded files; change only the engine list."""
    text = source.read_text() if text is None else text
    if '[tasks]' in text:
        raise ValueError('capture one task as a separate SBY file before replay')
    mode = re.search(r'(?m)^mode\s+(bmc|prove|cover)\s*$', text)
    depth = re.search(r'(?m)^depth\s+(\d+)\s*$', text)
    if not mode or not depth:
        raise ValueError('job must declare mode and depth')
    if not 1 <= len(engines) <= 2 or len(set(engines)) != len(engines):
        raise ValueError('select one or two distinct engines')
    inventory = installed()
    for name in engines:
        if name not in ENGINES or ENGINES[name][0] != 'sby':
            raise ValueError('replay needs SBY portfolio engines')
        if mode[1] == 'cover' and not name.startswith('smtbmc:'):
            raise ValueError('cover replay needs SMTBMC engines')
        if mode[1] != 'cover' and mode[1] not in ENGINES[name][2]:
            raise ValueError('engine does not support the original mode')
        if inventory[name]['status'] != 'installed':
            raise ValueError('engine is not installed: ' + name)
    directory.mkdir(parents=True, exist_ok=False)
    (directory/'original.sby').write_text(text)
    text, count = re.subn(r'(?ms)^\[engines\]\n.*?(?=^\[|\Z)',
                         '[engines]\n'+'\n'.join(n.replace(':',' ') for n in engines)+'\n\n', text)
    if count != 1:
        raise ValueError('job needs exactly one engines section')
    text = re.sub(r'(?ms)(^\[options\]\n)(.*?)(?=^\[|\Z)',
                  lambda m:m[1]+re.sub(r'(?m)^timeout\s+[^\n]+\n?', '', m[2]), text)
    text = re.sub(r'(?ms)(^\[script\]\n.*?)(?=^\[|\Z)',
                  lambda m:m[1]+'\nwrite_json replay-design.json\n\n',text)
    hashes = []
    bindings = {}
    def files(match):
        lines = []
        for line in match[1].splitlines():
            fields = shlex.split(line, comments=True)
            if not fields:
                continue
            if len(fields) not in (1,2):
                raise ValueError('unsupported SBY files entry')
            target, original = (Path(fields[0]).name, fields[0]) if len(fields)==1 else fields
            raw = (source.parent/original).read_bytes()
            bindings[(source.parent/original).resolve()]=target
            copy = directory/f'input-{len(hashes)}'
            copy.write_bytes(raw)
            hashes.append(dict(target=target, sha256=hashlib.sha256(raw).hexdigest()))
            lines.append(target+' '+str(copy.resolve()))
        return '[files]\n'+'\n'.join(lines)+'\n\n'
    text = re.sub(r'(?ms)^\[files\]\n(.*?)(?=^\[|\Z)', files, text)
    def script(match):
        def token(m):
            raw=m[0];word=raw.rstrip(';').strip('"')
            target=bindings.get((source.parent/word).resolve())
            return target+(';' if raw.endswith(';') else '') if target else raw
        return match[1]+re.sub(r'\S+',token,match[2])
    text=re.sub(r'(?ms)(^\[script\]\n)(.*?)(?=^\[|\Z)',script,text)
    (directory/'replay.sby').write_text(text)
    return mode[1], int(depth[1]), hashes


def path(root, value):
    return root/Path(os.path.expandvars(value)).expanduser()


def run(plan, root, out, limit):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    report = dict(schema='rvw.formal-timeout-rerun/1', rows=rows, time_limit_s=limit,
                  created_utc=datetime.now(timezone.utc).isoformat(),
                  limits=['Native engine results remain conditional on original source assumptions.',
                          'No activation or observer equivalence is inferred.',
                          'A remaining timeout is an unresolved capacity observation, not an absolute limit.'])
    for core in plan['cores']:
        try:
            receipt = path(root,core['previous']).read_bytes()
            previous = json.loads(receipt)
            for part in core.get('previous_pointer','').split('/')[1:]:
                part=part.replace('~1','/').replace('~0','~')
                previous=previous[int(part)] if isinstance(previous,list) else previous[part]
        except (OSError,ValueError,KeyError,IndexError) as exc:
            rows.append(dict(core=core['name'],check='receipt_inventory',status='error',comparison='not_run',
                             engine=None,wall_s=0,timeout_s=limit,load_average_start=load_average(),reason=str(exc)))
            continue
        selected = timed_out_checks(previous)
        jobs = core.get('checks', {})
        for check in selected:
            row = dict(core=core['name'], check=check, previous='timeout', status='not_run',
                       comparison='not_run', engine=None, wall_s=0, timeout_s=limit,
                       previous_sha256=hashlib.sha256(receipt).hexdigest(),
                       load_average_start=load_average())
            rows.append(row)
            directory = out/f'check-{len(rows):04d}'
            try:
                selection = jobs.get(check)
                task = selection.get('task') if isinstance(selection,dict) else None
                instruction=re.fullmatch(r'insn_(.+)_ch\d+(?:-activation)?',check)
                source = path(root,selection['sby'] if isinstance(selection,dict) else selection) if selection else path(root,core['jobs'])/core.get('job_pattern','{check}.sby').format(check=check,instruction=instruction[1] if instruction else check)
                text = source.read_text()
                if task:
                    config = run_group(['nice','-n','5','sby','--dumpcfg',source.name,task],
                                       cwd=source.parent,capture=True,timeout=30)
                    if config.timed_out or config.returncode:
                        raise ValueError('could not capture the selected SBY task')
                    text = config.stdout
                proof = re.search(r'(?m)^mode\s+prove\s*$', text)
                cover = re.search(r'(?m)^mode\s+cover\s*$', text)
                skip = re.search(r'(?m)^skip\s+[1-9]\d*\s*$',text)
                engines = core.get('engines') or (['abc:pdr','smtbmc:bitwuzla'] if proof else
                          ['smtbmc:bitwuzla','smtbmc:yices'] if cover or skip else ['abc:bmc3','smtbmc:bitwuzla'])
                mode, depth, hashes = freeze(source, directory, engines, text)
                row.update(mode=mode, depth=depth, source_sha256=hashes,
                           job_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
                began = time.monotonic()
                with (directory/'run.log').open('w') as log:
                    proc = run_group(['nice','-n','5','sby','-f','-d','sby','replay.sby'],
                                     cwd=directory, timeout=limit, stdout=log, stderr=log)
                row['wall_s'] = time.monotonic()-began
                text = (directory/'run.log').read_text()
                status = 'timeout' if proc.timed_out else parse_status('sby',text,proc.returncode,mode)
                model=directory/'sby/src/replay-design.json'
                row['assumptions']=[]
                if model.is_file():
                    from .proof_conditions import condition
                    count=0
                    for module,body in json.loads(model.read_text())['modules'].items():
                        for name,cell in body.get('cells',{}).items():
                            flavor=cell.get('parameters',{}).get('FLAVOR')
                            if cell['type']=='$assume' or (cell['type']=='$check' and flavor=='assume'):
                                row['assumptions'].append(condition(module,name,cell,model.parent))
                            kind='cover' if mode=='cover' else 'assert'
                            count+=cell['type']=='$'+kind or (cell['type']=='$check' and flavor==kind)
                    row['property_count']=count
                    row['condition_model_sha256']=hashlib.sha256(model.read_bytes()).hexdigest()
                    if status in ('pass','bounded_pass') and not count:
                        status='inconclusive';row['reason']='no_checks'
                elif status in ('pass','bounded_pass'):
                    status='inconclusive';row['reason']='missing_formal_model'
                if mode=='cover' and status=='bounded_pass' and not list((directory/'sby').glob('engine_*/trace*.vcd')):
                    status='inconclusive';row['reason']='missing_cover_trace'
                row['status'] = 'reached' if status=='bounded_pass' and mode=='cover' else status
                winner = re.search(r'engine_(\d+).*?returned (?:PASS|pass|FAIL|fail)',text)
                if winner and int(winner[1]) < len(engines):
                    row['engine'] = engines[int(winner[1])]
                closed = row['status'] in ('pass','bounded_pass','reached','fail')
                row['comparison'] = ('closed_after_retry' if closed else 'still_unresolved')
                row['load_average_end'] = load_average()
                row['low_load_at_endpoints'] = bool(row['load_average_start'] and row['load_average_end'] and
                    max(row['load_average_start'][0],row['load_average_end'][0])<=20)
                row['evidence'] = str(directory.relative_to(out))+'/run.log'
            except (OSError, ValueError, KeyError) as exc:
                row.update(status='error', reason=str(exc))
            (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
            (out/'comparison.md').write_text(table(rows))
    if not rows:
        report['reason'] = 'no_timeout_checks'
    report['status'] = 'inconclusive'
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'comparison.md').write_text(table(rows))
    return report


def table(rows):
    lines=['Core | Check | Depth | First engine | Seconds / limit | Result | Comparison | Load start / end',
           '--- | --- | --- | --- | --- | --- | --- | ---']
    for r in rows:
        lines.append(f"{r['core']} | {r['check']} | {r.get('depth','unknown')} | {r['engine']} | {r['wall_s']:.3f} / {r['timeout_s']:g} | {r['status']} | {r['comparison']} | {r['load_average_start']} / {r.get('load_average_end','unknown')}")
    return '\n'.join(lines)+'\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',type=Path)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--time-limit',default='30m',type=seconds)
    args=parser.parse_args()
    with sigterm_raises():
        report=run(json.loads(args.manifest.read_text()),args.manifest.resolve().parent,args.out,args.time_limit)
    print(table(report['rows']))
    return 1 if any(r['status']=='fail' for r in report['rows']) else 3


if __name__=='__main__':
    raise SystemExit(main())
