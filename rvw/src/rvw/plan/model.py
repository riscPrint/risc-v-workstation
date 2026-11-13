"""Roll up recorded evidence. Plan links do not prove requirement completeness."""
from hashlib import sha256
from pathlib import Path
import json
from rvw.cov import captured
from rvw.results import RunResult, Verdict, load_results
from rvw.common.verdicts import VERDICTS, producer_verdict, weakest_verdict


class VPlan:
    def __init__(self,path):
        self.path=Path(path).resolve()

    def read(self,reference):
        path=Path(reference['path'])
        if not path.is_absolute(): path=self.path.parent/path
        item=captured.file(path)
        if reference.get('sha256') and reference['sha256']!=item.sha256:
            raise ValueError('evidence hash differs: '+str(path))
        return path,json.loads(item.copy.read_text()),item.sha256

    @captured.command
    def status(self,previous=None):
        plan=json.loads(captured.read_text(self.path))
        if (plan.get('schema')!='rvw.vplan/1' or set(plan)-{'schema','requirements','features'}
                or not isinstance(plan.get('requirements'),dict) or not plan.get('features')):
            raise ValueError('expected rvw.vplan/1 with requirements and features')
        ids=[f['id'] for f in plan['features']]
        if not all(isinstance(i,str) and i for i in ids) or len(set(ids))!=len(ids):
            raise ValueError('feature IDs must be nonempty and unique')
        report={'schema':'rvw.plan-status/1','status':'reported','plan_sha256':captured.sha256(self.path),
                'features':[], 'notes':['Closure is a rollup of recorded evidence under project-declared links.',
                    'It does not establish requirement completeness, correct mappings, unconditional proof or C4 acceptance.']}
        if not all(isinstance(k,str) and k and isinstance(v,str) and v for k,v in plan['requirements'].items()):
            raise ValueError('requirements need nonempty IDs and descriptions')
        assigned=set()
        for feature in plan['features']:
            if (set(feature)-{'id','requirements','coverage','tests','formal','checks','scope'} or not feature.get('requirements')
                    or set(feature['requirements'])-plan['requirements'].keys()):
                raise ValueError('feature needs declared requirement IDs and known evidence fields')
            if feature.get('scope','integration') not in ('block','integration'):
                raise ValueError('feature scope must be block or integration')
            assigned.update(feature['requirements'])
            row={'id':feature['id'],'scope':feature.get('scope','integration'),'requirements':feature['requirements'],'evidence':[],'holes':[],
                 'coverage_hit':0,'coverage_expected':0,'coverage_contexts':[]}
            for role in ('coverage','tests','formal','checks'):
                for reference in feature.get(role,[]):
                    entry={'role':role,'path':reference['path'],'status':'inconclusive','verdict':'inconclusive'}
                    row['evidence'].append(entry)
                    try:
                        path,data,digest=self.read(reference)
                        entry['sha256']=digest
                        entry['verdict']=producer_verdict(data)
                        declared=data.get('verdict',data.get('status'))
                        # C1 tests need their typed inconclusive/timeout checks first.
                        if ((declared in VERDICTS or data.get('inconclusive')) and entry['verdict']!='pass'
                                and not (role=='tests' and data.get('schema')=='rvw.run/1')):
                            raise ValueError('producer verdict is '+entry['verdict'])
                        if role=='coverage': self.coverage(data,reference,row,entry)
                        elif role=='tests': self.tests(data,reference,path,row,entry)
                        elif role=='formal': self.formal(data,reference,path,row,entry)
                        else: self.check(data,reference,row,entry)
                    except (OSError,ValueError,KeyError,TypeError) as exc:
                        if entry['verdict']=='pass': entry['verdict']='inconclusive'
                        row['holes'].append({'role':role,'path':reference['path'],'reason':str(exc)})
            if not row['evidence']:
                row['holes'].append({'reason':'no evidence checks declared'})
            if row['scope']=='integration' and row['evidence'] and all(e.get('scope')=='block' for e in row['evidence']):
                row['holes'].append({'reason':'block evidence does not cover new integration wiring'})
            row['status']='reported_closed' if not row['holes'] else 'open'
            row['verdict']=weakest_verdict([e['verdict'] for e in row['evidence']]
                + (['inconclusive'] if row['holes'] else []))
            row['hole_count']=len(row['holes'])
            row['coverage_contexts']=sorted(set(row['coverage_contexts']))
            report['features'].append(row)
        report['unassigned_requirements']=sorted(plan['requirements'].keys()-assigned)
        report['verdict']=weakest_verdict([f['verdict'] for f in report['features']]
            + (['inconclusive'] if report['unassigned_requirements'] else []))
        report['summary']={'features':len(ids),'reported_closed':sum(f['status']=='reported_closed' for f in report['features']),
                           'open':sum(f['status']=='open' for f in report['features']),
                           'holes':sum(f['hole_count'] for f in report['features']),
                           'unassigned_requirements':len(report['unassigned_requirements'])}
        if previous:
            old=json.loads(captured.read_text(previous))
            if old.get('schema')!='rvw.plan-status/1' or old.get('plan_sha256')!=report['plan_sha256']:
                raise ValueError('trend requires the same verification plan')
            prior={f['id']:f for f in old['features']}
            for feature in report['features']:
                before=prior.get(feature['id'])
                if before and any(type(before.get(k)) is not int for k in ('hole_count','coverage_hit')):
                    raise ValueError('trend snapshot has invalid counts')
                if before and before.get('coverage_contexts')==feature['coverage_contexts']:
                    feature['trend']={'status':'comparable','hole_delta':feature['hole_count']-before['hole_count'],
                                      'coverage_hit_delta':feature['coverage_hit']-before['coverage_hit']}
                else: feature['trend']={'status':'incompatible_coverage_context'}
            report['previous_sha256']=captured.sha256(previous)
        return report

    def coverage(self,data,ref,row,entry):
        groups=ref.get('groups')
        if not groups or len(set(groups))!=len(groups):
            raise ValueError('coverage references need distinct explicit groups')
        schema=data.get('schema')
        if schema=='rvw.functional-coverage/1':
            trace_contexts=[{k:v for k,v in t['header'].items() if k not in ('elf','elf_sha256','seed')} for t in data.get('traces',{}).values()]
            context=sha256(json.dumps(sorted(trace_contexts,key=lambda t:json.dumps(t,sort_keys=True)),sort_keys=True).encode()).hexdigest()
            row['coverage_contexts'].append('functional:'+data['config_sha256']+':'+context)
            for name in groups:
                group=data['groups'][name]
                if any(type(group[k]) is not int or group[k]<0 for k in ('expected_hit','expected_bins')):
                    raise ValueError(name+': invalid coverage counts')
                if group['expected_hit']+len(group['holes'])!=group['expected_bins']:
                    raise ValueError(name+': inconsistent coverage denominator')
                if group['expected_bins']<=0: raise ValueError(name+': no fixed expected denominator')
                row['coverage_expected']+=group['expected_bins']
                row['coverage_hit']+=group['expected_hit']
                row['holes'] += [{'role':'coverage','group':name,'bin':b,'reason':'unobserved'} for b in group['holes']]
        elif schema=='rvw.probe-coverage/1':
            comparison=data.get('comparison',{})
            if (data.get('status')!='qualified' or comparison.get('status')!='match'
                    or comparison.get('trace_complete') is not True
                    or type(comparison.get('instructions')) is not int or comparison['instructions']<=0
                    or comparison.get('synchronized')!=0 or comparison.get('applied_masks')!=[]):
                raise ValueError('probe execution lacks complete strict reference qualification')
            row['coverage_contexts'].append('probe:'+data['plan_id']+':'+data['design'])
            records=[(b['id'],b['count']) for b in data['bins']]
            records += [(s['id'],s['completed']) for s in data.get('sequences',[])]
            if len({name for name,_ in records})!=len(records) or any(type(n) is not int or n<0 for _,n in records):
                raise ValueError('invalid probe goal counts')
            bins=dict(records)
            for name in groups:
                if name not in bins:raise ValueError('unknown probe goal: '+name)
                row['coverage_expected']+=1;row['coverage_hit']+=int(bins[name]>0)
                if not bins[name]:row['holes'].append({'role':'coverage','group':name,'reason':'unobserved'})
        elif schema=='rvw.rtl-coverage/1':
            if data.get('status')!='ok' or data.get('sampling_complete') is not True:
                raise ValueError('RTL samples are incomplete')
            row['coverage_contexts'].append('rtl:'+data['plan_id']+':'+data['design'])
            bins={b['id']:b['count']>0 for b in data['bins']}
            bins.update({s['id']:s['completed']>0 for s in data.get('sequences',[])})
            for name in groups:
                if name not in bins: raise ValueError('unknown RTL group: '+name)
                row['coverage_expected']+=1;row['coverage_hit']+=int(bins[name])
                if not bins[name]: row['holes'].append({'role':'coverage','group':name,'reason':'unobserved'})
        elif schema=='rvw.coverage/1':
            from rvw.cov.code import _require_conclusive
            _require_conclusive(data)
            native_contexts=sorted({json.dumps({key:run.get(key) for key in ('core','config','source','tools','rtl_sha256')},sort_keys=True)
                for test in data.get('tests',{}).values() if (run:=test.get('run'))})
            context=sha256(json.dumps([data.get('sources'),data.get('source_revision'),native_contexts],sort_keys=True).encode()).hexdigest()
            row['coverage_contexts'].append('code:'+data['point_universe']+':'+context)
            for name in groups:
                if '*' in name: raise ValueError('collapsed code scopes have no exact denominator')
                points=[p for p in data['points'] if p['fields'].get('h',p['fields'].get('hier'))==name]
                if not points: raise ValueError('unknown code coverage scope: '+name)
                if any(type(p['count']) is not int or p['count']<0 for p in points):
                    raise ValueError('invalid native coverage counts')
                row['coverage_expected']+=len(points);row['coverage_hit']+=sum(p['count']>0 for p in points)
                row['holes'] += [{'role':'coverage','group':name,'point':p['id'],'reason':'unobserved; exclusions not applied'} for p in points if not p['count']]
        else: raise ValueError('unsupported coverage schema')
        entry['status']='reported'

    def tests(self,data,ref,path,row,entry):
        if data.get('schema')=='rvw.run/1':
            run=RunResult.from_dict(data)
            if run.extra.get('details',{}).get('block_evidence'):
                entry['scope']='block'
            entry['verdict']='inconclusive' if run.why_inconclusive else producer_verdict(data)
            if entry['verdict']!='pass' or run.status!='pass':
                raise ValueError('C1 is not a conclusive pass: '+str(run.why_inconclusive or run.status))
        elif data.get('schema')=='rvw.results/1':
            suite=load_results(path)
            selected=[t for t in suite.tests if not ref.get('ids') or t.id in ref['ids']]
            if not selected or (ref.get('ids') and set(ref['ids'])-{t.id for t in selected}):
                raise ValueError('missing selected suite tests')
            entry['verdict']=weakest_verdict(['inconclusive' if not t.conclusive else
                producer_verdict(dict(t.extra,status=t.status)) for t in selected])
            if entry['verdict']!='pass' or any(t.status!='pass' for t in selected):
                raise ValueError('selected suite tests are not conclusive passes')
        else: raise ValueError('expected C1 or C3 test evidence')
        entry['status']='recorded_pass'

    def formal(self,data,ref,path,row,entry):
        if data.get('schema')!='rvw.formal-app-results/1' or not ref.get('properties'):
            raise ValueError('formal reference needs an app report and named properties')
        properties={p['property_id']:p for p in data['properties']}
        required=ref.get('proof_kind','unbounded')
        if required not in ('bounded','unbounded'): raise ValueError('unknown required proof kind')
        for identifier in ref['properties']:
            prop=properties[identifier]
            entry['verdict']=producer_verdict(prop)
            if entry['verdict']!='pass':
                raise ValueError(identifier+': property summary is '+entry['verdict'])
            child=path.parent/prop['result']
            if not child.resolve().is_relative_to(path.parent.resolve()): raise ValueError('property result escapes report')
            result=json.loads(captured.read_text(child))
            entry['verdict']=producer_verdict(result)
            if entry['verdict']!='pass':
                raise ValueError(identifier+': child verdict is '+entry['verdict'])
            if (result.get('schema')!='rvw.formal/1' or result.get('status')!='pass'
                    or result.get('proof_kind')!=required or type(result.get('assertions')) is not int or result['assertions']<=0
                    or (result.get('reachability') or {}).get('status')!='reachable'):
                raise ValueError(identifier+': missing conclusive '+required+' evidence')
            entry.setdefault('properties',[]).append({'id':identifier,'sha256':captured.sha256(child),
                                                     'restrictions':result.get('restrictions',[])})
            if prop['status']!='pass' or prop['proof_kind']!=required:
                raise ValueError(identifier+': property summary differs')
        entry.update(status='recorded_'+required+'_pass',assumptions='conditional; property activation not established')

    def check(self,data,ref,row,entry):
        kind=ref.get('kind')
        if kind=='gate':
            if not Verdict.from_dict(data).accepted: raise ValueError('C4 gate did not accept')
        elif kind=='block':
            if data.get('schema')!='rvw.block-reuse/1' or data.get('status')!='eligible_for_reuse' or data.get('holes'):
                raise ValueError('block reuse assumptions are not met')
            entry['scope']='block'
            entry['limitation']='new wiring remains uncovered'
        else: raise ValueError('check kind must be gate or block')
        entry['status']='recorded_satisfied'
        entry['verdict']='pass'
