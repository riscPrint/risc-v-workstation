"""Small UCB policy for measured code and RTL coverage goals."""
import math
import json
from pathlib import Path
from . import captured
from .rtl import identity, validate


class Guide:
    def __init__(self, plan, recipes, history=(), database=None):
        self.kind='code' if plan.get('schema')=='rvw.code-goals/1' else 'rtl'
        self.database=database
        if self.kind=='rtl':
            validate(plan)
            ids={b['id'] for b in plan['bins']} | {s['id'] for s in plan.get('sequences',[])}
            self.sequence_ids={s['id'] for s in plan.get('sequences',[])}
            self.full_ids=set(ids)
        else:
            if (set(plan)-{'schema','design','database','database_sha256','targets'}
                    or not database or database.get('schema')!='rvw.coverage/1'):
                raise ValueError('code goal plan needs a pinned code coverage database')
            self.full_ids={p['id'] for p in database['points']}
            ids=set(plan.get('targets',self.full_ids))
            if (not self.full_ids or len(self.full_ids)!=len(database['points']) or ids-self.full_ids
                    or len(ids)!=len(plan.get('targets',ids))):
                raise ValueError('code goals must name unique declared native points')
            if any(not source.get('sha256') for source in database['sources'].values()):
                raise ValueError('code goal database needs resolved source hashes')
            self.sequence_ids=set()
        if (set(recipes) != {'schema','plan_id','design','recipes'}
                or recipes['schema'] != 'rvw.event-recipes/1'
                or recipes['plan_id'] != identity(plan) or recipes['design'] != plan['design']):
            raise ValueError('recipes must bind the exact coverage plan and generated RTL')
        self.recipes, self.ids, self.history = {}, ids, list(history)
        self.plan_id, self.design = identity(plan), plan['design']
        for recipe in recipes['recipes']:
            if (set(recipe) != {'goal','targets'} or not recipe['goal']
                    or recipe['goal'] in self.recipes or not recipe['targets'] or set(recipe['targets'])-ids):
                raise ValueError('recipe needs a unique generator goal and declared '+('RTL' if self.kind=='rtl' else 'code')+' targets')
            self.recipes[recipe['goal']] = set(recipe['targets'])

    def pending_goals(self):
        observed = {hit for item in self.history for hit in item['new_events']}
        return {goal for goal,targets in self.recipes.items() if targets-observed}

    def choose(self, goals):
        observed = {hit for item in self.history for hit in item['new_events']}
        eligible = {goal for goal in goals if goal in self.recipes and self.recipes[goal]-observed}
        if not eligible:
            return sorted(goals)[0] if goals else None
        def score(goal):
            attempts = [h for h in self.history if h['goal']==goal]
            if not attempts:
                return float('inf')
            return sum(len(h['new_events']) for h in attempts)/len(attempts) + math.sqrt(
                2*math.log(len(self.history)+1)/len(attempts))
        return min(eligible, key=lambda goal: (-score(goal),goal))

    def observe(self, goal, report, *, qualified, rtl_sha256):
        """The execution controller owns qualification. Missing/stale samples earn none."""
        if not qualified:
            raise ValueError('coverage feedback requires a completely qualified execution')
        pending={}
        if self.kind=='rtl':
            if (rtl_sha256 != self.design or report.get('design') != self.design
                    or report.get('plan_id') != self.plan_id or report.get('schema') != 'rvw.rtl-coverage/1'
                    or report.get('status') != 'ok' or report.get('sampling_complete') is not True):
                raise ValueError('missing, incomplete or incompatible RTL sample identity')
            samples=[i['sha256'] for i in report.get('inputs',[])]
            observed={b['id'] for b in report['bins'] if b['count']>0}
            observed|={s['id'] for s in report.get('sequences',[]) if s['completed']>0}
            pending={s['id']:s['pending'] for s in report.get('sequences',[])}
        else:
            from .code import _require_conclusive
            if (rtl_sha256!=self.design or report.get('schema')!='rvw.coverage/1'
                    or report.get('point_universe')!=self.database['point_universe']
                    or {p['id'] for p in report.get('points',[])}!=self.full_ids):
                raise ValueError('incompatible native code point universe or RTL identity')
            _require_conclusive(report)
            static=lambda value:{p['id']:(p['key'],p['fields']) for p in value['points']}
            sources=lambda value:{key:pin['sha256'] for key,pin in value['sources'].items()}
            if static(report)!=static(self.database) or sources(report)!=sources(self.database):
                raise ValueError('native point semantics or source hashes changed')
            samples=[test['sha256'] for test in report['tests'].values()]
            observed={p['id'] for p in report['points'] if p['count']>0} & self.ids
        seen = {s for h in self.history for s in h['samples']}
        if not samples or len(set(samples)) != len(samples) or seen & set(samples):
            raise ValueError('missing or repeated coverage samples')
        if observed-self.ids:
            raise ValueError('samples contain unknown event goals')
        previous = {hit for item in self.history for hit in item['new_events']}
        result = {'goal':goal,'new_events':sorted(observed-previous),'samples':samples, 'pending_sequences':pending}
        self.history.append(result)
        return result


    def coverage_summary(self,generator_goals):
        observed={hit for item in self.history for hit in item['new_events']}
        reachable_recipes=set().union(*(targets for goal,targets in self.recipes.items() if goal in generator_goals)) if self.recipes else set()
        pending=next((h['pending_sequences'] for h in reversed(self.history) if 'pending_sequences' in h),{})
        return {'kind':self.kind,'plan_id':self.plan_id,'design':self.design,
                'declared_bins':len(self.ids),'full_input_bins':len(self.full_ids),
                'observed':sorted(observed),'unobserved':sorted(self.ids-observed),
                'uncompleted_sequences':sorted(self.sequence_ids-observed),
                'last_sample_pending':pending,'unsupported_targets':sorted(self.ids-reachable_recipes)}


@captured.command
def load_guide(plan_path,recipes_path,history=()):
    plan_path=Path(plan_path)
    plan=json.loads(captured.read_text(plan_path))
    database=None
    if plan.get('schema')=='rvw.code-goals/1':
        path=Path(plan['database'])
        if not path.is_absolute(): path=plan_path.parent/path
        if captured.sha256(path)!=plan['database_sha256']:
            raise ValueError('code goal database hash mismatch')
        database=json.loads(captured.read_text(path))
        for source in database['sources'].values():
            if not source.get('sha256') or captured.sha256(source['path'])!=source['sha256']:
                raise ValueError('code goal source hash mismatch')
    return Guide(plan,json.loads(captured.read_text(recipes_path)),history,database)
