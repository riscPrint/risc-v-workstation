"""Reach the selected instruction at its assertion cycle, not only any retirement."""
import json
from pathlib import Path
import re
import time
from rvw.common.proc import run_group
from .runtime import load_average, timeout_details


def cover_source(source, solver):
    if solver not in ('bitwuzla','yices','z3','boolector'):
        raise ValueError('unsupported activation solver')
    source, count = re.subn(r'(?m)^mode bmc$', 'mode cover', source)
    if count != 1:
        raise ValueError('activation needs one bounded checker mode')
    source = re.sub(r'(?m)^skip .*\n', '', source)
    return re.sub(r'(?s)(\[engines\]\n).*?(?=\n\[)',lambda m:m[1]+'smtbmc '+solver+'\n',source,count=1)


def run(cfg, directory, timeout):
    directory=Path(directory)
    suite=json.loads((directory/'results.json').read_text())
    work=directory/'riscv-formal/cores/project/checks'
    for entry in suite['tests']:
        name=entry['id']
        if not name.startswith('insn_'): continue
        activation=dict(status='error', reason='missing checker source')
        original=work/(name+'.sby')
        if original.is_file():
            file=work/(name+'-activation.sby')
            file.write_text(cover_source(original.read_text(),cfg['solver']))
            target=work/(name+'-activation')
            began=time.monotonic()
            load_start=load_average()
            try:
                with (directory/(name+'-activation.log')).open('w') as log:
                    result=run_group(['sby','-f',file.name],cwd=work,stdout=log,stderr=log,timeout=timeout)
                status=target/'status'
                tokens=status.read_text().split() if status.is_file() else []
                reached=bool(tokens and tokens[0]=='PASS' and result.returncode==0 and
                             not result.timed_out and list(target.glob('engine_*/trace*.vcd')))
                activation=dict(status='reached' if reached else 'timeout' if result.timed_out else 'inconclusive',
                                evidence=str(target.relative_to(directory)),
                                reason='' if reached else 'Selected instruction cover did not close with a trace.')
                activation.update(wall_s=time.monotonic()-began, timeout_s=timeout,
                                  load_average_start=load_start, load_average_end=load_average())
                if result.timed_out:
                    activation.update(timeout_details(activation['wall_s'],timeout,load_start))
            except OSError as exc:
                activation=dict(status='error',reason=str(exc))
        entry['instruction_activation']=activation
        if entry['status']=='pass' and activation['status']!='reached':
            entry['inconclusive']='Selected instruction was not independently reached at its assertion cycle.'
    (directory/'results.json').write_text(json.dumps(suite,indent=2)+'\n')
    verdict_path=directory/'verdict.json'
    if verdict_path.is_file() and any(t.get('inconclusive') for t in suite['tests']):
        verdict=json.loads(verdict_path.read_text())
        if verdict.get('tests')=='pass': verdict['tests']='incomplete'
        verdict.setdefault('reasons',[]).append('Selected instruction activation needs a reached cover trace.')
        verdict_path.write_text(json.dumps(verdict,indent=2)+'\n')
    return suite
