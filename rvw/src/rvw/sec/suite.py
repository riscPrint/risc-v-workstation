"""Collect bounded security reports without promoting samples to a proof."""
import json
from pathlib import Path
from .common import publish


def collect(reports,out):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    entries=[];findings=[]
    for index,file in enumerate(reports):
        try:
            r=json.loads(Path(file).read_text())
            if not isinstance(r,dict): raise ValueError('report must be an object')
            if r.get('schema')!='rvw.sec/1' or r.get('status') not in ('violation','no_leak_observed','inconclusive'):
                raise ValueError('expected executed rvw.sec/1 report')
            if r['status']=='no_leak_observed' and (r.get('complete') is not True or r.get('findings')):
                raise ValueError('clean report lacks complete evidence')
            if r['status']=='violation' and not r.get('findings'):
                raise ValueError('violation report lacks a finding')
            entry=dict(id=f'{index}-{r["technique"]}',report=str(Path(file).resolve()),
                       status={'violation':'fail','no_leak_observed':'pass','inconclusive':'error'}[r['status']],
                       message=r['status'],evidence_complete=r.get('complete') is True)
            if r['status']=='violation': findings.append(dict(report=str(file),findings=r['findings']))
            if entry['status']=='error': entry['inconclusive']='incomplete technique evidence'
        except (ValueError,OSError,KeyError) as e:
            entry=dict(id=str(index),status='error',message=str(e),inconclusive='invalid or missing report')
        if entry['status'] != 'pass': entry['signature']='sec:suite:'+entry['id']+':'+entry['status']
        entries.append(entry)
    result=publish(out,'suite',findings,bool(entries) and all(e.get('evidence_complete') is True for e in entries),
                   techniques=entries,limits='Sampled digital evidence. Never secure or proof.')
    suite=json.loads((out/'results.json').read_text());suite['tests']=entries
    (out/'results.json').write_text(json.dumps(suite,indent=2)+'\n')
    return result
