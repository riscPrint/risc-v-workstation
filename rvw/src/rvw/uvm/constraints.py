"""Optional Z3 constrained stimulus and declared functional coverage counters."""
from collections import Counter
from itertools import product
import random


class ConstraintSolver:
    """Bounded integer constraints. Seeded preferences are not uniform sampling."""
    def __init__(self, fields, constraints, *, seed=1, timeout_ms=1000):
        try:
            import z3
        except ImportError as exc:
            raise ValueError('install z3-solver for Python constrained stimulus') from exc
        self.z3, self.rng = z3, random.Random(seed)
        self.fields = dict(fields)
        if not self.fields or any(type(lo) is not int or type(hi) is not int or lo > hi
                                  for lo, hi in self.fields.values()):
            raise ValueError('fields need inclusive integer bounds')
        self.variables = {name:z3.Int(name) for name in self.fields}
        self.solver = z3.Solver()
        self.solver.set(timeout=timeout_ms, random_seed=seed)
        for name, (low, high) in self.fields.items():
            self.solver.add(self.variables[name] >= low, self.variables[name] <= high)
        self.solver.add(*constraints(self.variables))

    def sample(self):
        z3, solver = self.z3, self.solver
        status = solver.check()
        if status != z3.sat:
            raise ValueError('constraint solve '+str(status))
        solver.push()
        try:
            names = list(self.fields)
            self.rng.shuffle(names)
            for name in names:
                low, high = self.fields[name]
                preferred = self.variables[name] == self.rng.randint(low, high)
                status = solver.check(preferred)
                if status == z3.unknown:
                    raise ValueError('constraint solve unknown')
                if status == z3.sat:
                    solver.add(preferred)
            if solver.check() != z3.sat:
                raise ValueError('constraint solve failed')
            model = solver.model()
            return {name:model.eval(var).as_long() for name,var in self.variables.items()}
        finally:
            solver.pop()


class FunctionalCoverage:
    """Only sample observed transactions after their independent checks pass."""
    def __init__(self, domains):
        self.fields = list(domains)
        self.bins = list(product(*(domains[name] for name in self.fields)))
        if not self.bins or len(set(self.bins)) != len(self.bins):
            raise ValueError('declare nonempty unique functional bins')
        self.counts = Counter(dict.fromkeys(self.bins, 0))

    def sample(self, observation):
        key = tuple(observation[name] for name in self.fields)
        if key not in self.counts:
            raise ValueError('observation outside declared coverage bins')
        self.counts[key] += 1

    def export(self, *, context):
        from rvw.cov.exchange import validate
        import json
        return validate(dict(schema='rvw.coverage-exchange/1', context=context,
            status='reported', proof_exclusions_verified=False,
            rows=[dict(id='pyuvm:'+json.dumps(key,separators=(',',':')),kind='functional',
                       count=self.counts[key],metadata=dict(fields=self.fields,bin=list(key)))
                  for key in sorted(self.bins, key=lambda key:'pyuvm:'+json.dumps(key,separators=(',',':')))]))
