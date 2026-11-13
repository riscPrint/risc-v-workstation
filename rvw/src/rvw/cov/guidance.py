"""Small UCB policy for project-declared measured RTL event recipes."""
import math
from .rtl import identity, validate


class Guide:
    def __init__(self, plan, recipes, history=()):
        validate(plan)
        if (set(recipes) != {'schema','plan_id','design','recipes'}
                or recipes['schema'] != 'rvw.event-recipes/1'
                or recipes['plan_id'] != identity(plan) or recipes['design'] != plan['design']):
            raise ValueError('recipes must bind the exact sampling plan and generated RTL')
        ids = {b['id'] for b in plan['bins']} | {s['id'] for s in plan.get('sequences',[])}
        self.recipes, self.ids, self.history = {}, ids, list(history)
        self.plan_id, self.design = identity(plan), plan['design']
        for recipe in recipes['recipes']:
            if (set(recipe) != {'goal','targets'} or not recipe['goal']
                    or recipe['goal'] in self.recipes or not recipe['targets'] or set(recipe['targets'])-ids):
                raise ValueError('recipe needs a unique generator goal and declared RTL targets')
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
            raise ValueError('RTL feedback requires a completely qualified execution')
        if (rtl_sha256 != self.design or report.get('design') != self.design
                or report.get('plan_id') != self.plan_id or report.get('schema') != 'rvw.rtl-coverage/1'
                or report.get('status') != 'ok' or report.get('sampling_complete') is not True):
            raise ValueError('missing, incomplete or incompatible RTL sample identity')
        samples = [i['sha256'] for i in report.get('inputs',[])]
        seen = {s for h in self.history for s in h['samples']}
        if not samples or len(set(samples)) != len(samples) or seen & set(samples):
            raise ValueError('missing or repeated RTL samples')
        observed = {b['id'] for b in report['bins'] if b['count'] > 0}
        observed |= {s['id'] for s in report.get('sequences',[]) if s['completed'] > 0}
        if observed-self.ids:
            raise ValueError('samples contain unknown event goals')
        previous = {hit for item in self.history for hit in item['new_events']}
        result = {'goal':goal,'new_events':sorted(observed-previous),'samples':samples}
        self.history.append(result)
        return result
