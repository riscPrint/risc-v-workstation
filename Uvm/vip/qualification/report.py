"""Render the measured native matrix without promoting incomplete runs."""
import argparse
import json
from types import SimpleNamespace
from run import checked, assessment
from pathlib import Path


def render(data):
    lines = ['# SV protocol runtime qualification', '',
             'Engine: '+data['engine']+'.',
             'Accellera revision: `'+data['uvm_commit']+'` with `UVM_NO_DPI`.', '',
             '| Agent | Compiles | Good DUT | Bad DUT detected | Other fault checks |',
             '|---|---|---|---|---|']
    notes = []
    for row in data['agents']:
        runs = row['runs']
        def status(selected):
            if not selected:
                return 'not established'
            return f"{sum(r['checked'] for r in selected)}/{len(selected)}"
        baseline=assessment(runs)['runs_good']
        corrupt_status=status([r for r in runs if r['fault']=='buggy'])
        if not baseline and corrupt_status!='not established':
            corrupt_status+=' diagnostics; not established'
        lines.append('| '+ ' | '.join([row['agent'], 'yes' if row['compiles'] else 'no',
            status([r for r in runs if not r['negative']]),
            corrupt_status,
            status([r for r in runs if r['negative'] and r['fault']!='buggy'])])+' |')
        if row.get('limitation'):
            notes += ['', row['agent']+': '+row['limitation']]
        failures = [r for r in runs if not r['checked']]
        if failures:
            notes += ['', row['agent']+': incomplete cases: '+', '.join(f"seed {r['seed']} {r['fault'] or 'good'}" for r in failures)+'. Inspect the retained logs.']
    return '\n'.join(lines+notes+['',
        'Each runtime case uses seeds 1, 2 and 3. Builds use two compiler jobs and a 1800-second limit.',
        'A bad-DUT detection claim also requires every normal good-DUT baseline run to pass.',
        'Good runs require one completion marker and no UVM error or fatal. Bad runs require the declared diagnostic, nonzero exit and no completion marker.',
        'The fixtures establish only their declared digital profiles. Native model stubs are not protocol implementations.',
        'No CPU, ISA, physical link or commercial VIP qualification follows from these results.', ''])


def aliases(value,mapping):
    if isinstance(value,str):
        for source,target in mapping:
            value=value.replace(source,target)
        return value
    if isinstance(value,list):return [aliases(v,mapping) for v in value]
    if isinstance(value,dict):return {aliases(k,mapping):aliases(v,mapping) for k,v in value.items()}
    return value


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('matrix', type=Path)
    p.add_argument('out', type=Path)
    p.add_argument('--merge', type=Path, action='append', default=[])
    p.add_argument('--json-out', type=Path)
    p.add_argument('--path-alias',action='append',default=[],metavar='PATH=TOKEN')
    a = p.parse_args()
    data=json.loads(a.matrix.read_text())
    by_agent={row['agent']:(row,a.matrix.parent) for row in data['agents']}
    for matrix in a.merge:
        newer=json.loads(matrix.read_text())
        if newer['engine']!=data['engine'] or newer['uvm_commit']!=data['uvm_commit']:
            raise ValueError('cannot merge different engine/library campaigns')
        by_agent.update((row['agent'],(row,matrix.parent)) for row in newer['agents'])
    for row,folder in by_agent.values():
        for run in row['runs']:
            marker=next(r['diagnostic'] for r in row['runs'] if r['fault']=='')
            text=(folder/row['agent']/run['log']).read_text(errors='replace')
            run['checked']=checked(text,SimpleNamespace(**run),marker,run['diagnostic'],run['negative'])
            if not run['checked']:
                run['observed_diagnostic']='\n'.join(line for line in text.splitlines()
                    if ('UVM_FATAL ' in line and ':    0' not in line) or '%Fatal' in line or '%Error' in line)[-2000:]
            run['evidence_directory']=str(folder/row['agent'])
        row.update(assessment(row['runs']))
        for key,negative in [('all_good_cases',False),('all_fault_cases',True)]:
            rows=[r for r in row['runs'] if r['negative']==negative]
            row[key]=bool(rows) and all(r['checked'] for r in rows)
    data['agents']=[by_agent[key][0] for key in sorted(by_agent)]
    data=aliases(data,[entry.split('=',1) for entry in a.path_alias])
    a.out.write_text(render(data))
    if a.json_out:
        a.json_out.write_text(json.dumps(data,indent=2)+'\n')
